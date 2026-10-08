# Day 33 — Multimodal: Images, Documents and Voice

> ⏱ **Time:** ~3 hours · 🎯 **Prereqs:** [Day 32](day-32-dataset-engineering.md), [Day 04](../week-01-foundations/day-04-langchain-models.md) (content blocks) · 🧩 **Difficulty:** ●●●○○

**Today you learn:** Students don't only type. They photograph the whiteboard, upload slides
full of diagrams, and send voice notes from the bus. StudyBuddy can't use any of that yet,
because everything you have built so far reads text. Today you give it eyes and ears. You
send images to a model as LangChain **content blocks**, and run a small **vision-language
model** on your own CPU. You turn speech into text with **Whisper** and text back into speech.
You index pictures for **multimodal RAG**, and time a whole **voice pipeline**. At the end,
StudyBuddy v6.5 accepts a photo, a voice note or typed text.

Every output below was run on a laptop CPU with no API key, unless it is labelled
*not executed*.

> 📖 **Words you'll meet today**
>
> - **Modality** — one kind of input or output: text, image, audio or video.
> - **Vision-language model (VLM)** — a model that reads images and text together and answers
>   in text.
> - **Content block** — one typed piece of a message, such as `{type: "text"}` or
>   `{type: "image"}`. A message can hold several.
> - **Base64** — a way to write any file as plain letters and digits, so it fits inside JSON.
> - **Image tokens** — the tokens a model makes from a picture. You pay for them like text tokens.
> - **Speech-to-text (STT)** — turning recorded speech into written words. Also called
>   transcription.
> - **Text-to-speech (TTS)** — turning written words into recorded speech.
> - **Sample rate** — how many times per second a sound was measured. Whisper expects 16,000.

---

## 1. The problem

StudyBuddy v6.4 is fast and well tested. Then exam week arrives, and the support inbox fills up:

```
   08:10  "I sent a photo of my notes and it said: I can't see images."
   09:25  lecture-07.pdf indexed → the cell diagram on page 3 became 0 characters of text
   09:26  student asks "what does the diagram on page 3 show?" → "I don't have that information"
   11:40  a voice note (4 s) arrives from the bus → rejected: "unsupported file type"
   13:05  a student with dyslexia asks for answers read aloud → no way to do it
```

Nothing is broken. StudyBuddy was built for text, and a lot of study material isn't text. A
diagram has no words for the loader to extract (Day 09 warned you about this). A photo is
pixels. A voice note is a list of air-pressure numbers.

### The real-life version

Imagine two tutors. The first only reads typed emails. You must describe your diagram in words,
type out your notes, and never ask a question out loud. The second tutor looks at your notebook,
listens to your question and answers out loud.

Both know the same biology. The second one is far more useful, because the student doesn't do
the conversion work. Today StudyBuddy becomes the second tutor. You will also see that
"looking" and "listening" cost time and money, and sometimes go wrong.

---

## 2. Mental model

Every model works on **tokens**. Multimodal models simply have more ways to make them:

```
   TEXT   "What is this?"  ──► tokenizer ─────────────────────────► text tokens ─┐
                                                                                  │
   IMAGE  pixels ──► cut into tiles/patches ──► vision encoder ──► image tokens ─┼─► one model
                                                                                  │   reads them
   AUDIO  samples (16 kHz) ──► spectrogram ──► audio encoder ──► audio features ─┘   all
```

You have two ways to use a picture or a sound:

```
   NATIVE:      [photo] ─────────────────────────────► VLM ──► answer
   CONVERT:     [photo] ──► describe / read text ──► words ──► any text model ──► answer
                [voice] ──► speech-to-text ──────► words ──► any text model ──► text-to-speech
```

| | Native (send the image or audio itself) | Convert first (caption, OCR, transcribe) |
|---|---|---|
| Keeps details | Yes — layout, colour, arrows | Only what the converter wrote down |
| Cost per question | Image tokens on **every** call | Paid **once**, at ingest time |
| Works with | Vision or audio models only | Any text model, any vector store |
| Easy to debug | Harder — you can't read pixels in a log | Easy — the text is in your logs |
| Typical use | One-off questions about a photo | RAG over many documents, voice pipelines |

Most real systems mix both. They convert for search, then send the original picture to a VLM
when the student asks about it. That is §3.7.

---

## 3. First principles

### 3.1 How a model "sees": patches become tokens

> 💬 **In plain words:** the model cuts a picture into small squares. A small network turns
> each group of squares into a token, and the language model reads those tokens like words.

A 2020 Google paper (Dosovitskiy et al., *An Image is Worth 16x16 Words*) showed a simple idea.
Cut the image into 16×16-pixel **patches**, and a transformer can read each patch like a word.
Most vision-language models still work this way.

The model we run today is **SmolVLM-256M-Instruct**, a 256-million-parameter VLM from Hugging
Face. Its config files (read from the downloaded model) say:

```
   image_size 512 · patch_size 16 · scale_factor 4 · max_image_size.longest_edge 512
```

So one 512×512 tile holds 32 × 32 = 1,024 patches. The model then merges each 4×4 group of
patches into one token (a trick called *pixel shuffle*), which leaves **64 image tokens per
tile**. We counted the image tokens the processor actually produced:

```
   size        splitting OFF   splitting ON
   256x256          64             1088
   384x256          64              832
   1024x768         64              832
   2048x1536        64              832
```

Two surprises. With splitting **off**, every image costs 64 tokens, whatever its size. The
model squeezes it into one tile. With splitting **on** (the model's default), the processor
first **enlarges** the image so its longest side is 2,048 pixels. It then cuts it into
512-pixel tiles and adds one small overview tile. A 256×256 picture became 16 + 1 = 17 tiles =
1,088 tokens. A tiny image is not automatically cheap.

### 3.2 Image tokens cost money

> 💬 **In plain words:** a picture becomes hundreds or thousands of tokens, and hosted
> providers charge for them like text. Each provider counts them its own way.

Each provider publishes its own rule. Two examples, read from their documentation in October
2026 (rules change — check the current page before you budget):

| Provider | Rule (quoted from the docs) | A 1000×1000 photo |
|---|---|---|
| Google Gemini | "258 tokens if both dimensions <= 384 pixels. Larger images are tiled into 768x768 pixel tiles, each costing 258 tokens." | several tiles × 258 |
| Anthropic Claude | an image costs `⌈width / 28⌉ × ⌈height / 28⌉` visual tokens | 36 × 36 = **1,296** tokens |

The Gemini page adds that "Gemini 3 introduces granular control over multimodal vision
processing with the `media_resolution` parameter". This course uses `gemini-3.8-flash`, so its
image count can differ from the 258-token rule. The page doesn't say exactly which models use
which rule. Check it for your model, or read `usage_metadata` after a real call.

Compare that with the question itself. "What is on this page?" is about 6 tokens. The photo is
often **100 times bigger** than the question. If StudyBuddy resends the photo on every turn of
a conversation, you pay for it every time. [Day 34](day-34-cost-and-latency.md) builds the cost
ledger that catches this.

The bytes grow too. Base64 writes every 3 bytes as 4 characters. Our 3,739-byte test PNG
became **4,988** base64 characters (measured; 4,988 ÷ 3,739 = 1.33). Providers also cap the
request size. Gemini's documentation limits a request with inline images to 20 MB in total.

### 3.3 The resolution trade-off

> 💬 **In plain words:** more pixels let the model read small text, but cost more tokens and
> more time. Fewer pixels are cheap, but small text turns into a guess.

We asked SmolVLM to read the whiteboard image below twice: once with splitting off (64 image
tokens) and once with splitting on (576 image tokens).

```
   ┌─────────────────────────────────┐
   │  PHOTOSYNTHESIS                 │      notes.png, 512 × 256 pixels,
   │  light + water + CO2            │      drawn with code (§4.1)
   └─────────────────────────────────┘
```

| Run (CPU, our machine) | Input tokens | Time | Answer to "What text is written in this image?" |
|---|---|---|---|
| JS, splitting off | 83 | 2.3 s | "The text is written in a sans-serif font." |
| JS, splitting on | 613 | 23.1 s | "Photosynthesis is light + water + CO2" |
| Python, splitting off | 83 | 4.0 s | "Light + water + CO2" |
| Python, splitting on | 613 | 26.8 s | "PHOTOSYNTHESIS light + water + CO2" |

*(Times include loading the model on first use. The JS run uses 8-bit weights and the Python
run uses 32-bit weights, as in [Day 29](day-29-open-and-local-models.md).)*

With splitting off, both languages missed part of the text. With splitting on, both read it,
and it took about **7 times** as many tokens and **6–10 times** as long. In an earlier
Python run on a Pillow-drawn copy of the same notes, with splitting off, the model said the
image was "a photograph of a light bulb". A
small model that can't see clearly doesn't say "I can't read this". It guesses.

> 🎯 **Rule of thumb:** shrink photos to the smallest size that keeps the text readable to
> *you*. Then test that size on your real images. Text-heavy images need more detail than
> pictures of objects.

### 3.4 The content block: one shape for every provider

> 💬 **In plain words:** in LangChain, an image travels inside a message as a small object:
> its type, its data, and its file type. LangChain turns that object into each provider's format.

[Day 04](../week-01-foundations/day-04-langchain-models.md) showed that a message's `content` can
be a list of blocks. LangChain 1.x has a standard image block. JS and Python spell its keys
differently:

```js
{ type: "image", data: "<base64>", mimeType: "image/png" }          // JS
```

```python
{"type": "image", "base64": "<base64>", "mime_type": "image/png"}  # Python
```

You will also meet two older spellings: the OpenAI-style data URL
(`{type: "image_url", image_url: {url: "data:image/png;base64,..."}}`) and the LangChain 0.3
form (`{type: "image", source_type: "base64", data, mime_type}`). We sent all three to a
scripted model that reports what it received:

```
   JS     model received:  image keys=type,data,mimeType              (v1, as written)
                           image_url keys=type,image_url              (data URL, as written)
                           image keys=type,source_type,data,mime_type (0.3 form, as written)
   Python model received:  image keys=type,base64,mime_type           (v1)
                           image_url keys=type,image_url              (data URL, as written)
                           image keys=type,base64,mime_type           (0.3 form — CONVERTED)
```

The languages differ here. Python's chat model converts the old 0.3 form into the v1 form
before your model sees it. JS passes all three through unchanged. Both languages offer a
normalised view — `.contentBlocks` in JS and `.content_blocks` in Python. All three
spellings came out as the same v1 image block there. **When you write a model or a
middleware, read the normalised view, not `.content`.**

Two traps belong here, because LangChain does **not** check your data:

- **A `data:` prefix in the base64 field** was accepted silently by `HumanMessage` in both
  languages (measured). See §7, mistake 1.
- **A wrong MIME type** (`image/jpeg` on a PNG) was passed straight to the provider (measured
  on the request body). The MIME type must describe the real bytes.

### 3.5 How a model "hears": 16,000 numbers per second

> 💬 **In plain words:** recorded sound is a long list of numbers. Whisper expects exactly
> 16,000 of them per second. If you give it a different rate, it hears a sped-up or slowed-down
> voice.

A microphone measures air pressure many times per second. That count is the **sample rate**.
Phones often record at 44,100 or 48,000 per second; old telephone audio uses 8,000. **Whisper**
is OpenAI's open speech-recognition model. It was trained on 680,000 hours of audio (Radford
et al., 2022). Its preprocessing config says:

```
   sampling_rate 16000 · chunk_length 30 (seconds) · feature_size 80 (frequency bands)
```

So Whisper listens in **30-second windows** of 16 kHz audio. It first turns the sound into a
*spectrogram* — a picture of which frequencies are loud at each moment. It never checks the
rate itself; you must convert first. We recorded the same question at three rates and fed it
to Whisper-tiny **without** converting:

```
   question.wav    16,000 Hz → "What is the difference between mitosis and myosis?"   (JS)
   question44k.wav 44,100 Hz → "You can't stop the force. You can't stop the force."   (JS)
   question44k.wav 44,100 Hz → "Yeah, cool, cool, cool, cool, cool, ..." (hundreds of "cool")  (Python)
   question8k.wav   8,000 Hz → "What's the difference between my goals and my goals?"  (JS)
```

No error was raised. Wrong-rate audio produced confident nonsense. In Python it caused a
repetition loop that took 25–40 seconds (two runs). Notice the first line too: even correct audio gave "myosis" instead
of "meiosis" with 8-bit weights in JS. The 32-bit Python model heard "meiosis" correctly.

### 3.6 Speaking back: text-to-speech

> 💬 **In plain words:** text-to-speech turns the answer into a sound file. Long answers make
> long recordings, so voice replies must be short.

Text-to-speech runs the other way: words in, samples out. Cloud providers offer natural voices.
Open models exist too. We used the voice engine **built into Windows** (System.Speech), because
it needs no download. It wrote our 4.38-second test question in 0.5–1.2 s (four runs). That
time includes starting PowerShell.

The speed is fine. The length is the real problem. A 40-token answer became **14.64 s** of
audio in our pipeline (§4.8). Nobody wants to listen to a paragraph. Voice answers need their
own prompt: one or two short sentences, no lists, no symbols that read badly aloud.

### 3.7 Multimodal RAG: index the words, keep a pointer to the picture

> 💬 **In plain words:** a vector store searches words. So you write a description of each
> picture, search the descriptions, and keep a link back to the original picture.

Day 12's RAG pipeline embeds text. A diagram has no text, so it is invisible to search. The
common fix has three steps:

```
   INGEST    picture ──► VLM: "describe this, copy any text exactly" ──► caption
             store Document(pageContent = caption, metadata = {page, image: "fig-3.png"})
   RETRIEVE  question ──► vector search over captions AND normal text chunks
   ANSWER    retrieved text + the ORIGINAL picture (from metadata) ──► VLM ──► answer
```

The caption is the search key. The picture itself goes to the answering model, so details the
caption missed are still available. Two other designs exist. **Multimodal embeddings** (for
example CLIP) put images and text in one vector space, so you can search pictures directly.
**Page screenshots** treat every PDF page as an image, which keeps tables and layout.
Captioning is the simplest and works with every vector store you already know. It's the one we
build (§4.7). The other two are *not executed* here.

> 🔒 Text inside an image is still untrusted input. A photo of a page saying "ignore your
> instructions" is a prompt injection that never appears in your text logs.
> [Day 35](day-35-ai-security.md) covers the defences.

### 3.8 The voice pipeline and its latency budget

> 💬 **In plain words:** a voice assistant is three models in a row. The student waits for
> all three, and a mistake in the first one flows into the others.

```
   🎤 audio ──► STT (Whisper) ──► text ──► LLM ──► reply text ──► TTS ──► 🔊 audio
               ~0.9–1.2 s               ~1.2–2.7 s             ~0.6–0.8 s
```

We timed two full turns in each language on this laptop's CPU (§4.8, §5.8):

| Stage | JS (8-bit models) | Python (32-bit models) | Measured or illustrative? |
|---|---|---|---|
| STT — Whisper-tiny, 4.38 s of audio | 1,200 / 1,136 ms | 909 / 998 ms | measured |
| LLM — SmolLM2-135M, 40 new tokens | 1,267 / 1,223 ms | 2,262 / 2,738 ms | measured |
| TTS — Windows System.Speech | 627 / 601 ms | 684 / 809 ms | measured |
| **Total before any sound plays** | **3,094 / 2,960 ms** | **3,855 / 4,545 ms** | measured |
| A target for natural conversation | about 1 s | about 1 s | **illustrative** |

Three lessons come from this table:

1. **Errors flow downstream.** The JS pipeline heard "myosis", and the LLM answered about
   "mitosis and myosis". Nothing later in the pipeline can fix a mishearing.
2. **The stages add up.** To get closer to a conversational pace, real voice apps *stream*:
   they start speaking the first sentence while the model writes the second (Day 23's
   streaming, applied to audio).
3. **Speech-to-speech models** skip the middle text step and respond to audio directly. They
   are faster and hear tone of voice, but they are harder to log, test and ground in your
   documents. *Not executed here.*

### 3.9 Image generation: when a picture is the output

> 💬 **In plain words:** an image model turns a text description into a new picture. Use it
> for illustrations, not for facts.

Image generation runs the other direction: a text prompt in, a new image out. Most current
models use *diffusion*. They start from random noise and remove it step by step, guided by the
prompt. Uses that fit StudyBuddy: a cover picture for a study set, or an illustrative cartoon
for a revision card.

Uses that don't fit: anything that must be **correct**. A generated "labelled diagram of a
cell" can have wrong labels, made-up structures or misspelled words. For accurate diagrams,
draw them with code or retrieve real ones. Generated images also cost much more per call than
text. They raise copyright and safety questions too, so label them as AI-generated.

---

## 4. Code — JavaScript

You need Node 20+ and about 700 MB of disk for the two small models. No API key is needed.

```bash
npm i @langchain/core @langchain/classic @huggingface/transformers wavefile
# only for §4.3 and §4.9 (hosted providers):  npm i @langchain/google-genai openai
```

> 📦 Transformers.js downloads each model once and caches it. Set `env.cacheDir` to choose
> the folder, and `dtype` to choose the weight size ([Day 29](day-29-open-and-local-models.md)
> §4.2). We use `dtype: "q8"` (8-bit) throughout. `sharp`, the image library used below, is
> installed with `@huggingface/transformers`.

### 4.1 Make test images with code

You don't need a camera. Draw the test images from SVG, so every reader gets the same pixels:

```js
// make-images.mjs — a "diagram" and a "whiteboard photo", drawn with code
import sharp from "sharp";

const shapes = `
<svg xmlns="http://www.w3.org/2000/svg" width="384" height="256">
  <rect width="384" height="256" fill="white"/>
  <circle cx="96" cy="128" r="64" fill="red"/>
  <rect x="224" y="64" width="128" height="128" fill="blue"/>
</svg>`;
const png = await sharp(Buffer.from(shapes)).png().toBuffer();
await sharp(png).toFile("shapes.png");
console.log("bytes:", png.length, "| base64 chars:", png.toString("base64").length);

const notes = `
<svg xmlns="http://www.w3.org/2000/svg" width="512" height="256">
  <rect width="512" height="256" fill="white"/>
  <text x="24" y="90" font-family="Arial" font-size="44" fill="black">PHOTOSYNTHESIS</text>
  <text x="24" y="170" font-family="Arial" font-size="36" fill="black">light + water + CO2</text>
</svg>`;
await sharp(Buffer.from(notes)).png().toFile("notes.png");
```

Output:

```
bytes: 3739 | base64 chars: 4988
```

### 4.2 A safe image block, and what the model receives

Your code should check an image **before** it spends money on a provider call. Read the first
bytes of the file (its *magic number*) to learn the real format. Don't trust the file name.

```js
// image-block.mjs — build a safe image content block from a file
import { readFileSync } from "node:fs";

const MAGIC = [                                   // the first bytes of each format
  ["image/png", [0x89, 0x50, 0x4e, 0x47]],
  ["image/jpeg", [0xff, 0xd8, 0xff]],
  ["image/gif", [0x47, 0x49, 0x46, 0x38]],
  ["image/webp", [0x52, 0x49, 0x46, 0x46]],       // "RIFF" (WebP also has "WEBP" at byte 8)
];
const MAX_BYTES = 5 * 1024 * 1024;                 // pick a limit below your provider's

export function sniffMime(bytes) {
  for (const [mime, sig] of MAGIC) if (sig.every((b, i) => bytes[i] === b)) {
    if (mime === "image/webp" && bytes.toString("latin1", 8, 12) !== "WEBP") return null;  // WAV is RIFF too
    return mime;
  }
  return null;
}

export function imageBlock(path) {
  const bytes = readFileSync(path);
  const mimeType = sniffMime(bytes);
  if (!mimeType) throw new Error(`${path}: not a PNG/JPEG/GIF/WebP file`);
  if (bytes.length > MAX_BYTES) throw new Error(`${path}: ${bytes.length} bytes is over ${MAX_BYTES}`);
  return { type: "image", data: bytes.toString("base64"), mimeType };   // raw base64, no "data:" prefix
}
```

> ⚠️ **A bug we caught by running it.** The first version only checked the four `RIFF` bytes
> for WebP. Our `question.wav` was accepted as `image/webp`, because WAV files also start with
> `RIFF`. The `WEBP` check at byte 8 fixed it.

Now send the block to a scripted model that reports what arrived (the Day 22 pattern):

```js
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage, HumanMessage } from "@langchain/core/messages";
import { imageBlock } from "./image-block.mjs";

class Inspector extends BaseChatModel {          // no key, no network
  _llmType() { return "inspector"; }
  async _generate(messages) {
    const parts = messages.at(-1).contentBlocks.map((b) =>
      b.type === "text" ? `text(${b.text.length} chars)` : `${b.type}(${b.mimeType}, ${b.data.length} base64 chars)`);
    const message = new AIMessage({ content: parts.join(" + ") });
    return { generations: [{ message, text: message.content }] };
  }
}

const msg = new HumanMessage({ content: [
  { type: "text", text: "What shapes are in this picture?" },
  imageBlock("shapes.png"),
]});
console.log((await new Inspector({}).invoke([msg])).text);

for (const p of ["notes.png", "fake.png", "question.wav"]) {   // fake.png holds plain text
  try { console.log(p, "→", imageBlock(p).mimeType); }
  catch (e) { console.log(p, "→", e.message); }
}
```

Output:

```
text(32 chars) + image(image/png, 4988 base64 chars)
notes.png → image/png
fake.png → fake.png: not a PNG/JPEG/GIF/WebP file
question.wav → question.wav: not a PNG/JPEG/GIF/WebP file
```

### 4.3 The hosted call: Gemini (free tier) or Ollama

With a key, the same message goes to a hosted vision model. Gemini's free tier accepts images:

```js
// Needs GOOGLE_API_KEY. The live call was NOT executed; the request it sends was captured below.
import { ChatGoogleGenerativeAI } from "@langchain/google-genai";
import { HumanMessage } from "@langchain/core/messages";
import { imageBlock } from "./image-block.mjs";

const model = new ChatGoogleGenerativeAI({ model: "gemini-3.8-flash", temperature: 0 });
const res = await model.invoke([new HumanMessage({ content: [
  { type: "text", text: "What text is written in this image? Copy it exactly." },
  imageBlock("notes.png"),
]})]);
console.log(res.text);
console.log(res.usage_metadata);   // image tokens are inside input_tokens
```

We didn't call Google, but we did check what LangChain **would send**. We replaced
`fetch` with a function that records the request and returns a fake reply. Both the v1 block
and the data-URL form became the same Gemini request:

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent
parts: [{"text":"What shapes are in this picture?"},{"inlineData":{"mimeType":"image/png","data":"<4988 chars>"}}]
```

The same capture showed the two silent traps from §3.4. A `data:` prefix inside `data` was
sent as-is (`"data:image/png;base64,iVB..."`), and so was a wrong `mimeType: "image/jpeg"`.
The provider gets bad data, and your code got no warning.

To run fully offline instead, a vision model in Ollama takes the same message (*not executed
here — Ollama isn't installed on this machine*):

```js
import { ChatOllama } from "@langchain/ollama";
const local = new ChatOllama({ model: "llava" });   // after: ollama pull llava
```

<details>
<summary>💰 Paid alternatives</summary>

`ChatOpenAI` (`@langchain/openai`) and `ChatAnthropic` (`@langchain/anthropic`) accept the
same standard image block. Pick a vision-capable model from the provider's current model list.
Read its image token rule (§3.2) before you send many images. *Not executed here.*
</details>

### 4.4 A local vision model as a LangChain chat model

Day 29 wrapped a local text model in `BaseChatModel`. The same idea works for a VLM. The
wrapper reads LangChain's normalised `contentBlocks` and converts them into what SmolVLM
expects. Then any chain, agent or graph can use it.

```js
// local-vision.mjs — a LangChain chat model that can SEE, running on your CPU
import { AutoProcessor, AutoModelForImageTextToText, RawImage } from "@huggingface/transformers";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { AIMessage } from "@langchain/core/messages";

export class LocalVision extends BaseChatModel {
  constructor({ model = "HuggingFaceTB/SmolVLM-256M-Instruct", maxNewTokens = 40, split = false } = {}) {
    super({});
    Object.assign(this, { modelId: model, maxNewTokens, split });
  }
  _llmType() { return "local-vision"; }

  async _generate(messages) {
    this.processor ??= await AutoProcessor.from_pretrained(this.modelId);
    this.vlm ??= await AutoModelForImageTextToText.from_pretrained(this.modelId, { dtype: "q8" });

    // 1. Turn LangChain content blocks into the model's own chat format + a list of images
    const images = [];
    const chat = [];
    for (const m of messages) {
      const content = [];
      for (const b of m.contentBlocks) {
        if (b.type === "text") content.push({ type: "text", text: b.text });
        else if (b.type === "image") {
          const blob = new Blob([Buffer.from(b.data, "base64")], { type: b.mimeType });
          images.push(await RawImage.fromBlob(blob));
          content.push({ type: "image" });        // a placeholder; the processor fills it
        }
      }
      chat.push({ role: m.getType() === "ai" ? "assistant" : "user", content });
    }

    // 2. Run the model
    const prompt = this.processor.apply_chat_template(chat, { add_generation_prompt: true });
    const inputs = await this.processor(prompt, images, { do_image_splitting: this.split });
    const nIn = inputs.input_ids.dims.at(-1);
    const out = await this.vlm.generate({ ...inputs, max_new_tokens: this.maxNewTokens, do_sample: false });
    const [text] = this.processor.batch_decode(out.slice(null, [nIn, null]), { skip_special_tokens: true });

    const message = new AIMessage({
      content: text.trim(),
      usage_metadata: { input_tokens: nIn, output_tokens: out.dims.at(-1) - nIn, total_tokens: out.dims.at(-1) },
    });
    return { generations: [{ message, text: message.content }] };
  }
}
```

Use it exactly like a hosted model:

```js
import { HumanMessage } from "@langchain/core/messages";
import { imageBlock } from "./image-block.mjs";
import { LocalVision } from "./local-vision.mjs";

const vision = new LocalVision();                 // splitting off: 64 image tokens
for (const [file, question] of [
  ["shapes.png", "What shapes and colours are in this image?"],
  ["notes.png", "What text is written in this image?"],
]) {
  const res = await vision.invoke([new HumanMessage({ content: [
    { type: "text", text: question },
    imageBlock(file),
  ]})]);
  console.log(file, "→", res.text);
  console.log("  usage:", res.usage_metadata);
}

const big = new LocalVision({ split: true });     // splitting on: more tiles, more detail
const res = await big.invoke([new HumanMessage({ content: [
  { type: "text", text: "What text is written in this image?" }, imageBlock("notes.png")] })]);
console.log("notes.png split →", res.text, res.usage_metadata);
```

Output (first download took about 4 minutes; after that, times as in §3.3):

```
shapes.png → The image is a simple, flat, and colorful image. It consists of a red circle and a blue square. The red circle is on the left side of the image and the blue square is on
  usage: { input_tokens: 84, output_tokens: 40, total_tokens: 124 }
notes.png → The text is written in a sans-serif font.
  usage: { input_tokens: 83, output_tokens: 14, total_tokens: 97 }
notes.png split → Photosynthesis is light + water + CO2 { input_tokens: 613, output_tokens: 11, total_tokens: 624 }
```

The shapes answer is right but was cut off at 40 tokens. Without splitting, the notes answer
dodged the question. With splitting, it read both lines. Small models are like that: useful,
but you check their work. In another run we put the image *before* the question, and the
unsplit model answered `The text in this image is "PHOTOSYNTHESIS".` Prompt order matters too.

### 4.5 Speech-to-text with Whisper

Whisper needs a `Float32Array` of 16 kHz mono samples. `wavefile` reads a WAV file and converts
the sample rate for you:

```js
// stt.mjs — transcribe WAV files with Whisper-tiny on the CPU
import { readFileSync } from "node:fs";
import wavefile from "wavefile";
import { pipeline } from "@huggingface/transformers";

// Read a WAV file into the Float32Array (mono, 16 kHz) that Whisper expects.
function readWav(path, { resample = true } = {}) {
  const wav = new wavefile.WaveFile(readFileSync(path));
  const rate = wav.fmt.sampleRate;
  wav.toBitDepth("32f");                       // 16-bit integers → floats in [-1, 1]
  if (resample) wav.toSampleRate(16000);       // Whisper was trained on 16 kHz audio
  let samples = wav.getSamples();
  if (Array.isArray(samples)) samples = samples[0];   // stereo → keep the first channel
  return { samples: new Float32Array(samples), rate, seconds: samples.length / (resample ? 16000 : rate) };
}

const stt = await pipeline("automatic-speech-recognition", "onnx-community/whisper-tiny.en", { dtype: "q8" });

for (const [file, resample] of [["question.wav", true], ["question44k.wav", true], ["question44k.wav", false]]) {
  const { samples, rate, seconds } = readWav(file, { resample });
  const t = performance.now();
  const { text } = await stt(samples);
  console.log(`${file} (${rate} Hz, resample=${resample}) ${seconds.toFixed(2)}s → ${Math.round(performance.now() - t)} ms:${text}`);
}
```

The WAV files come from §4.6 (`question44k.wav` uses `-Rate 44100`). Output:

```
question.wav (16000 Hz, resample=true) 4.38s → 696 ms: What is the difference between mitosis and myosis?
question44k.wav (44100 Hz, resample=true) 4.38s → 631 ms: What is the difference between mitosis and myosis?
question44k.wav (44100 Hz, resample=false) 4.38s → 669 ms: You can't stop the force. You can't stop the force.
```

The first load took 28 s (download); later loads took about 2 s. Whisper transcribed 4.38 s of
speech in 0.6–2.5 s across our runs; the slow runs happened while other programs were busy.
It is faster than real time, even on a CPU. With
the sample rate converted, it heard the question (apart from "myosis"). Without the
conversion, it invented a sentence.

### 4.6 Text-to-speech with the voice built into Windows

> 🪟 **Windows only.** This uses System.Speech, which ships with Windows. On macOS, the `say`
> command does a similar job. On Linux, try `espeak-ng` or an open TTS model. Neither was
> executed here.

```powershell
# say.ps1 — text to a 16 kHz mono WAV file with the voice built into Windows
param([Parameter(Mandatory)][string]$Text, [string]$Out = "reply.wav", [int]$Rate = 16000)
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$format = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(
  $Rate, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,
  [System.Speech.AudioFormat.AudioChannel]::Mono)
$synth.SetOutputToWaveFile([IO.Path]::GetFullPath($Out), $format)
$synth.Speak($Text)
$synth.Dispose()
```

We made the test question with it:
`pwsh -File say.ps1 -Text "What is the difference between mitosis and meiosis?" -Out question.wav`
(and again with `-Rate 44100` and `-Rate 8000`). Call it from Node:

```js
// say.mjs
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import wavefile from "wavefile";

export function say(text, out = "reply.wav") {
  // execFile passes the text as ONE argument: no shell, so no command injection
  execFileSync("pwsh", ["-NoProfile", "-File", "say.ps1", "-Text", text, "-Out", out]);
  const wav = new wavefile.WaveFile(readFileSync(out));
  return wav.data.chunkSize / wav.fmt.byteRate;     // seconds of audio written
}

const t = performance.now();
const seconds = say("Mitosis makes two identical cells. Meiosis makes four different ones.");
console.log(`wrote ${seconds.toFixed(2)} s of audio in ${Math.round(performance.now() - t)} ms`);
```

Output (three runs): `wrote 7.00 s of audio in 610 ms`, then 600 ms, then 599 ms.

> 🔒 The answer text comes from a model, so treat it as untrusted. `execFileSync` with an
> argument list never starts a shell. Building a command string such as
> `` `pwsh say.ps1 -Text "${answer}"` `` would let a crafted answer run commands.

> ⚠️ Once, `pwsh` crashed with `Fatal error. Internal CLR error. (0x80131506)` and the call
> threw. The next run worked. TTS is an external process that can fail, so give it the
> Day 24 treatment: a timeout, one retry, and a text fallback.

### 4.7 Multimodal RAG: describe, index, retrieve, answer with the picture

This is §3.7 in code. The describer is scripted so it runs without a key. Swap in
`LocalVision` or Gemini later — same interface. The embedder is a tiny keyless one that hashes
words into 256 slots. It's good enough to show the flow. Day 10's real embeddings do much better.

```js
// mm-rag.mjs — multimodal RAG: describe pictures, index the words, answer with the picture
import { Document } from "@langchain/core/documents";
import { Embeddings } from "@langchain/core/embeddings";
import { HumanMessage, AIMessage } from "@langchain/core/messages";
import { BaseChatModel } from "@langchain/core/language_models/chat_models";
import { FakeListChatModel } from "@langchain/core/utils/testing";
import { MemoryVectorStore } from "@langchain/classic/vectorstores/memory";
import { imageBlock } from "./image-block.mjs";

// A keyless embedder: hash each word into one of 256 slots (good enough for a demo)
class HashEmbeddings extends Embeddings {
  constructor() { super({}); }
  vec(text) {
    const v = new Array(256).fill(0);
    for (const w of text.toLowerCase().match(/[a-z0-9]+/g) ?? []) {
      let h = 0; for (const c of w) h = (h * 31 + c.charCodeAt(0)) >>> 0;
      v[h % 256] += 1;
    }
    const n = Math.hypot(...v) || 1;
    return v.map((x) => x / n);
  }
  async embedDocuments(texts) { return texts.map((t) => this.vec(t)); }
  async embedQuery(text) { return this.vec(text); }
}

// The study pack: some pages are text, some are pictures
const pack = [
  { kind: "text", page: 1, text: "Cells divide by mitosis to grow and repair tissue." },
  { kind: "image", page: 2, image: "notes.png" },
  { kind: "image", page: 3, image: "shapes.png" },
  { kind: "text", page: 4, text: "Area of a circle is pi times the radius squared." },
];

// 1. INGEST — a vision model writes a description of each picture.
//    Scripted here (no key); swap in LocalVision or Gemini — same interface.
const describer = new FakeListChatModel({ responses: [
  "Whiteboard notes. Title: PHOTOSYNTHESIS. Below: light + water + CO2.",
  "A diagram with a red circle on the left and a blue square on the right.",
]});
const docs = [];
for (const item of pack) {
  if (item.kind === "text") {
    docs.push(new Document({ pageContent: item.text, metadata: { page: item.page, kind: "text" } }));
  } else {
    const caption = (await describer.invoke([new HumanMessage({ content: [
      { type: "text", text: "Describe this study image for a search index. Copy any text exactly." },
      imageBlock(item.image),
    ]})])).text;
    docs.push(new Document({ pageContent: caption,                       // the WORDS get embedded
      metadata: { page: item.page, kind: "image", image: item.image } })); // a pointer to the PICTURE
  }
}
const store = await MemoryVectorStore.fromDocuments(docs, new HashEmbeddings());

// 2. RETRIEVE — words in, words out
const question = "What do plants need for photosynthesis?";
const hits = await store.similaritySearchWithScore(question, 2);
for (const [d, s] of hits) console.log(s.toFixed(3), d.metadata, "|", d.pageContent);

// 3. ANSWER — send the retrieved text AND the original picture to a vision model
class Inspector extends BaseChatModel {          // scripted: reports what it was given
  _llmType() { return "inspector"; }
  async _generate(messages) {
    const blocks = messages.at(-1).contentBlocks;
    const kinds = blocks.map((b) => b.type).join(", ");
    const message = new AIMessage({ content: `received ${blocks.length} blocks: ${kinds}` });
    return { generations: [{ message, text: message.content }] };
  }
}
const content = [{ type: "text", text:
  `Answer from the sources. Cite pages.\nQuestion: ${question}\n\n` +
  hits.map(([d]) => `[page ${d.metadata.page}] ${d.pageContent}`).join("\n") }];
for (const [d] of hits) if (d.metadata.image) content.push(imageBlock(d.metadata.image));
console.log((await new Inspector({}).invoke([new HumanMessage({ content })])).text);
```

Output:

```
0.144 { page: 2, kind: 'image', image: 'notes.png' } | Whiteboard notes. Title: PHOTOSYNTHESIS. Below: light + water + CO2.
0.000 { page: 1, kind: 'text' } | Cells divide by mitosis to grow and repair tissue.
received 2 blocks: text, image
```

The question has no words in common with the picture itself. It matched the **caption**, and
the answer step got the original image back through `metadata.image`. Notice the second hit:
a score of 0.000 means no shared words at all, yet it was still returned. Exercise 4 adds a
score threshold.

### 4.8 A voice pipeline with a stopwatch

Now chain §4.5, a small local LLM and §4.6, and time each stage:

```js
// voice.mjs — speech in, speech out: STT → LLM → TTS, with a stopwatch on each stage
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import wavefile from "wavefile";
import { pipeline } from "@huggingface/transformers";

function readWav(path) {
  const wav = new wavefile.WaveFile(readFileSync(path));
  wav.toBitDepth("32f");
  wav.toSampleRate(16000);
  let s = wav.getSamples();
  if (Array.isArray(s)) s = s[0];
  return new Float32Array(s);
}

function say(text, out) {
  execFileSync("pwsh", ["-NoProfile", "-File", "say.ps1", "-Text", text, "-Out", out]);
  const wav = new wavefile.WaveFile(readFileSync(out));
  return wav.data.chunkSize / wav.fmt.byteRate;
}

const timer = () => { const t = performance.now(); return () => Math.round(performance.now() - t); };

let done = timer();
const stt = await pipeline("automatic-speech-recognition", "onnx-community/whisper-tiny.en", { dtype: "q8" });
const llm = await pipeline("text-generation", "HuggingFaceTB/SmolLM2-135M-Instruct", { dtype: "q8" });
console.log("load both models:", done(), "ms");

async function voiceTurn(inFile, outFile) {
  const times = {};
  done = timer();
  const audio = readWav(inFile);
  const { text: question } = await stt(audio);
  times.stt = done();

  done = timer();
  const out = await llm([
    { role: "system", content: "You are StudyBuddy. Answer in one short sentence." },
    { role: "user", content: question.trim() },
  ], { max_new_tokens: 40, do_sample: false });
  const answer = out[0].generated_text.at(-1).content;
  times.llm = done();

  done = timer();
  const replySeconds = say(answer, outFile);           // §4.6
  times.tts = done();
  return { question: question.trim(), answer, times, audioIn: audio.length / 16000, replySeconds };
}

for (let i = 0; i < 2; i++) {
  const r = await voiceTurn("question.wav", "reply.wav");
  console.log(`turn ${i + 1}:`, JSON.stringify(r.times), `total=${r.times.stt + r.times.llm + r.times.tts} ms`);
  if (i === 0) {
    console.log("  heard: ", r.question);
    console.log("  said:  ", r.answer);
    console.log(`  audio in ${r.audioIn.toFixed(2)} s, reply audio ${r.replySeconds.toFixed(2)} s`);
  }
}
// Check the TTS output by transcribing it back
console.log("reply.wav transcribed back:", (await stt(readWav("reply.wav"))).text);
```

Output:

```
load both models: 1329 ms
turn 1: {"stt":1200,"llm":1267,"tts":627} total=3094 ms
  heard:  What is the difference between mitosis and myosis?
  said:   Mitosis and myosis are two related but distinct processes in the cell cycle. Mitosis is the process of cell division, where the cell divides into two daughter cells, each with the same number of
  audio in 4.38 s, reply audio 14.64 s
turn 2: {"stt":1136,"llm":1223,"tts":601} total=2960 ms
reply.wav transcribed back:  mitosis and myosis are too related but distinct processes in the cell cycle. Mitosis is the process of cell division, where the cell divides into two daughter cells, each with the same number of.
```

Read this output like an incident report:

- The mishearing ("myosis") flowed into the answer. The LLM even explained "myosis" as a cell
  process. A real system should confirm uncertain words first (Exercise 5).
- The system prompt asked for one short sentence. The small model wrote a paragraph, and
  `max_new_tokens: 40` cut it off mid-sentence. The student would **hear** the cut-off.
- The answer is 14.64 s of audio for a 4.38 s question.
- Transcribing the reply back is a cheap self-test: you can check TTS output in CI without
  listening to it.

### 4.9 Image generation

The OpenAI SDK's `images.generate` returns the picture as base64. We ran this code against a
**local stand-in server** that returns our test PNG, so the request and the decoding were
verified. The real provider call was *not executed* here.

```js
// image-gen.mjs — ask an image model for a picture and save it
import { writeFileSync } from "node:fs";
import OpenAI from "openai";
import { sniffMime } from "./image-block.mjs";

const client = new OpenAI();                 // reads OPENAI_API_KEY; we used baseURL → a local fake
const result = await client.images.generate({
  model: "gpt-image-1",                      // illustrative — check your provider's current model list
  prompt: "A simple labelled diagram of a plant cell, flat colours, white background",
  size: "1024x1024",
  n: 1,
});
const bytes = Buffer.from(result.data[0].b64_json, "base64");
writeFileSync("generated.png", bytes);
console.log("saved generated.png:", bytes.length, "bytes,", sniffMime(bytes));
```

What the local server received, and what the code printed:

```
server got: POST /v1/images/generations {"model":"gpt-image-1","prompt":"A simple labelled diagram of a plant cell, flat colours, white background","size":"1024x1024","n":1}
saved generated.png: 3739 bytes, image/png
```

Check the bytes with `sniffMime` before you store or show a generated file, just as you do
for uploads. Remember §3.9: this prompt asks for a *labelled* diagram, and generated labels can
be wrong. Show it as an illustration, never as a source.

---

## 5. Code — Python

Same examples, same order. You need Python 3.10+ and about 900 MB of disk for the models (the
Python VLM uses 32-bit weights).

```bash
pip install langchain-core transformers torch pillow numpy
# only for §5.3 and §5.9 (hosted providers):  pip install langchain-google-genai openai
```

> 📦 Python's `transformers` downloads to the Hugging Face cache (set `HF_HOME` to move it).
> Reading WAV files uses the standard library's `wave` module plus NumPy. Nothing else is needed.

### 5.1 Make test images with code

```python
# make_images.py — a "diagram" and a "whiteboard photo", drawn with code
import base64, io
from PIL import Image, ImageDraw, ImageFont

img = Image.new("RGB", (384, 256), "white")
d = ImageDraw.Draw(img)
d.ellipse((32, 64, 160, 192), fill="red")          # a red circle
d.rectangle((224, 64, 352, 192), fill="blue")      # a blue square
img.save("shapes.png")
buf = io.BytesIO(); img.save(buf, format="PNG")
print("bytes:", len(buf.getvalue()), "| base64 chars:", len(base64.b64encode(buf.getvalue())))

notes = Image.new("RGB", (512, 256), "white")
d = ImageDraw.Draw(notes)
d.text((24, 50), "PHOTOSYNTHESIS", fill="black", font=ImageFont.load_default(size=44))
d.text((24, 140), "light + water + CO2", fill="black", font=ImageFont.load_default(size=36))
notes.save("notes.png")
```

Output:

```
bytes: 1337 | base64 chars: 1784
```

Pillow compresses this simple picture into fewer bytes than sharp did (3,739). The drawing is
the same, but the fonts and the PNG encoder differ. The measurements in the rest of this section
used the **JS-made** PNG files, so both languages saw identical pixels. With your own Pillow
images, byte counts differ and a small model's answers may change too.

### 5.2 A safe image block, and what the model receives

```python
# image_block.py — build a safe image content block from a file
import base64
from pathlib import Path

MAGIC = [                                           # the first bytes of each format
    ("image/png", b"\x89PNG"),
    ("image/jpeg", b"\xff\xd8\xff"),
    ("image/gif", b"GIF8"),
    ("image/webp", b"RIFF"),                        # WebP also has b"WEBP" at byte 8
]
MAX_BYTES = 5 * 1024 * 1024                         # pick a limit below your provider's


def sniff_mime(data: bytes) -> str | None:
    mime = next((mime for mime, sig in MAGIC if data.startswith(sig)), None)
    if mime == "image/webp" and data[8:12] != b"WEBP":   # WAV files start with RIFF too
        return None
    return mime


def image_block(path: str) -> dict:
    data = Path(path).read_bytes()
    mime_type = sniff_mime(data)
    if not mime_type:
        raise ValueError(f"{path}: not a PNG/JPEG/GIF/WebP file")
    if len(data) > MAX_BYTES:
        raise ValueError(f"{path}: {len(data)} bytes is over {MAX_BYTES}")
    return {"type": "image", "base64": base64.b64encode(data).decode(), "mime_type": mime_type}
```

```python
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from image_block import image_block


class Inspector(GenericFakeChatModel):
    """A scripted model that reports what it received — no key, no network."""
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        parts = [f"text({len(b['text'])} chars)" if b["type"] == "text"
                 else f"{b['type']}({b['mime_type']}, {len(b['base64'])} base64 chars)"
                 for b in messages[-1].content_blocks]
        return ChatResult(generations=[ChatGeneration(message=AIMessage(" + ".join(parts)))])


msg = HumanMessage(content=[
    {"type": "text", "text": "What shapes are in this picture?"},
    image_block("shapes.png"),
])
print(Inspector(messages=iter([])).invoke([msg]).text)

for p in ["notes.png", "fake.png", "question.wav"]:        # fake.png holds plain text
    try:
        print(p, "→", image_block(p)["mime_type"])
    except ValueError as e:
        print(p, "→", e)
```

Output:

```
text(32 chars) + image(image/png, 4988 base64 chars)
notes.png → image/png
fake.png → fake.png: not a PNG/JPEG/GIF/WebP file
question.wav → question.wav: not a PNG/JPEG/GIF/WebP file
```

### 5.3 The hosted call: Gemini (free tier) or Ollama

```python
# Needs GOOGLE_API_KEY. The live call was NOT executed; the request it sends was captured below.
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from image_block import image_block

model = ChatGoogleGenerativeAI(model="gemini-3.8-flash", temperature=0)
res = model.invoke([HumanMessage(content=[
    {"type": "text", "text": "What text is written in this image? Copy it exactly."},
    image_block("notes.png"),
])])
print(res.text)
print(res.usage_metadata)   # image tokens are inside input_tokens
```

We captured the request by patching `httpx.Client.send` to record it and return a fake reply.
Both the v1 block and the data-URL form became the same Gemini request:

```
POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent
parts: [{'text': 'What shapes are in this picture?'}, {'inlineData': {'mime_type': 'image/png', 'data': 'iVBORw0KGgoAAAANSUhEUgAAA...'}}]
```

The traps behave differently from JS. A wrong `mime_type: "image/jpeg"` was again sent without
complaint. But a `data:` prefix inside `base64` failed **before** sending:

```
binascii.Error: Invalid base64-encoded string: number of data characters (5005) cannot be 1 more than a multiple of 4
```

Python's Gemini integration decodes the base64 itself, so the prefix breaks it. That is a
confusing message for a simple mistake (§7, mistake 1).

For a fully local run, Ollama's vision model takes the same message (*not executed here*):

```python
from langchain_ollama import ChatOllama
local = ChatOllama(model="llava")   # after: ollama pull llava
```

<details>
<summary>💰 Paid alternatives</summary>

`ChatOpenAI` (`langchain-openai`) and `ChatAnthropic` (`langchain-anthropic`) accept the same
standard image block. Pick a vision-capable model from the provider's current list and read its
image token rule (§3.2). *Not executed here.*
</details>

### 5.4 A local vision model as a LangChain chat model

```python
# local_vision.py — a LangChain chat model that can SEE, running on your CPU
import base64, io
import torch
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class LocalVision(BaseChatModel):
    model_id: str = "HuggingFaceTB/SmolVLM-256M-Instruct"
    max_new_tokens: int = 40
    split: bool = False                              # image splitting: more tiles, more detail

    @property
    def _llm_type(self) -> str:
        return "local-vision"

    def _load(self):
        if not hasattr(self, "_vlm"):
            object.__setattr__(self, "_processor", AutoProcessor.from_pretrained(
                self.model_id, do_image_splitting=self.split))
            object.__setattr__(self, "_vlm", AutoModelForImageTextToText.from_pretrained(
                self.model_id, dtype=torch.float32))

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._load()
        # 1. Turn LangChain content blocks into the model's chat format + a list of images
        images, chat = [], []
        for m in messages:
            content = []
            for b in m.content_blocks:
                if b["type"] == "text":
                    content.append({"type": "text", "text": b["text"]})
                elif b["type"] == "image":
                    raw = base64.b64decode(b["base64"])
                    images.append(Image.open(io.BytesIO(raw)).convert("RGB"))
                    content.append({"type": "image"})     # a placeholder; the processor fills it
            chat.append({"role": "assistant" if m.type == "ai" else "user", "content": content})

        # 2. Run the model
        prompt = self._processor.apply_chat_template(chat, add_generation_prompt=True)
        inputs = self._processor(text=prompt, images=images or None, return_tensors="pt")
        n_in = inputs["input_ids"].shape[1]
        with torch.no_grad():
            out = self._vlm.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False)
        text = self._processor.batch_decode(out[:, n_in:], skip_special_tokens=True)[0].strip()
        n_out = out.shape[1] - n_in
        msg = AIMessage(content=text, usage_metadata={
            "input_tokens": n_in, "output_tokens": n_out, "total_tokens": n_in + n_out})
        return ChatResult(generations=[ChatGeneration(message=msg)])
```

> 💡 `object.__setattr__` stores the loaded model on the instance without Pydantic checking
> it. LangChain chat models are Pydantic models, so a plain `self._vlm = ...` is rejected for
> undeclared fields.

```python
from langchain_core.messages import HumanMessage
from image_block import image_block
from local_vision import LocalVision

vision = LocalVision()                            # splitting off: 64 image tokens
for file, question in [
    ("shapes.png", "What shapes and colours are in this image?"),
    ("notes.png", "What text is written in this image?"),
]:
    res = vision.invoke([HumanMessage(content=[
        {"type": "text", "text": question},
        image_block(file),
    ])])
    print(file, "→", res.text)
    print("  usage:", res.usage_metadata)

big = LocalVision(split=True)                     # splitting on: more tiles, more detail
res = big.invoke([HumanMessage(content=[
    {"type": "text", "text": "What text is written in this image?"}, image_block("notes.png")])])
print("notes.png split →", res.text, res.usage_metadata)
```

Output (first download about 5.5 minutes; then times as in §3.3):

```
shapes.png → Circle and Square
  usage: {'input_tokens': 84, 'output_tokens': 4, 'total_tokens': 88}
notes.png → Light + water + CO2
  usage: {'input_tokens': 83, 'output_tokens': 7, 'total_tokens': 90}
notes.png split → PHOTOSYNTHESIS light + water + CO2 {'input_tokens': 613, 'output_tokens': 15, 'total_tokens': 628}
```

Same model and same token counts as JS, but different answers. The weights differ: 32-bit
here, 8-bit in JS. Both languages needed splitting to read the title.

### 5.5 Speech-to-text with Whisper

```python
# stt.py — transcribe WAV files with Whisper-tiny on the CPU
import time, wave
import numpy as np
from transformers import pipeline

def read_wav(path):
    """Read a 16-bit PCM WAV into float32 samples in [-1, 1] plus its sample rate."""
    with wave.open(path, "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    samples = pcm.reshape(-1, channels)[:, 0].astype(np.float32) / 32768.0
    return samples, rate

stt = pipeline("automatic-speech-recognition", model="openai/whisper-tiny.en", device="cpu")

def run(label, payload):
    t = time.perf_counter()
    try:
        text = stt(payload)["text"]
    except Exception as e:
        text = f"{type(e).__name__}: {str(e)[:200]}"
    print(f"{label} → {(time.perf_counter() - t) * 1000:.0f} ms:{text}")

s16, r16 = read_wav("question.wav")
run("16k dict", {"raw": s16, "sampling_rate": r16})
s44, r44 = read_wav("question44k.wav")
run("44.1k dict (declared)", {"raw": s44, "sampling_rate": r44})
run("44.1k bare array (undeclared)", s44)
run("file path", "question.wav")
```

Output (the long line is shortened):

```
16k dict → 1098 ms: What is the difference between mitosis and meiosis?
44.1k dict (declared) → 0 ms:ImportError: torchaudio is required to resample audio samples in AutomaticSpeechRecognitionPipeline. The torchaudio package can be installed through: `pip install torchaudio`.
44.1k bare array (undeclared) → 25053 ms: Yeah, cool, cool, cool, cool, cool, cool, cool, ... (hundreds more)
file path → 22 ms:ValueError: ffmpeg was not found but is required to load audio files from filename
```

Four lessons in four lines:

- **Correct input works** — and the 32-bit model heard "meiosis" correctly.
- **Declaring the rate is good, but resampling needs `torchaudio`.** The pipeline told you
  exactly that instead of guessing. Install it, or record at 16 kHz.
- **A bare array is assumed to be 16 kHz.** The wrong rate produced 25 seconds of "cool"
  (40 seconds in an earlier run).
- **A file path needs ffmpeg** on your PATH. Reading the WAV yourself avoids that dependency.

### 5.6 Text-to-speech with the voice built into Windows

Reuse `say.ps1` from §4.6 (🪟 Windows only).

```python
# say.py
import subprocess, time, wave

def say(text, out="reply.wav"):
    # a list of arguments and no shell=True: the text can't become a command
    subprocess.run(["pwsh", "-NoProfile", "-File", "say.ps1", "-Text", text, "-Out", out], check=True)
    with wave.open(out, "rb") as w:
        return w.getnframes() / w.getframerate()      # seconds of audio written

t = time.perf_counter()
seconds = say("Mitosis makes two identical cells. Meiosis makes four different ones.")
print(f"wrote {seconds:.2f} s of audio in {(time.perf_counter() - t) * 1000:.0f} ms")
```

Output (three runs): `wrote 7.00 s of audio in 651 ms`, then 650 ms, then 671 ms. `check=True` turns a
crashed `pwsh` into a `CalledProcessError` you can catch and retry.

### 5.7 Multimodal RAG: describe, index, retrieve, answer with the picture

```python
# mm_rag.py — multimodal RAG: describe pictures, index the words, answer with the picture
import math, re
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.vectorstores import InMemoryVectorStore
from image_block import image_block


class HashEmbeddings(Embeddings):
    """A keyless embedder: hash each word into one of 256 slots (good enough for a demo)."""
    def _vec(self, text):
        v = [0.0] * 256
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            h = 0
            for c in w:
                h = (h * 31 + ord(c)) % 2**32
            v[h % 256] += 1
        n = math.sqrt(sum(x * x for x in v)) or 1
        return [x / n for x in v]
    def embed_documents(self, texts): return [self._vec(t) for t in texts]
    def embed_query(self, text): return self._vec(text)


pack = [
    {"kind": "text", "page": 1, "text": "Cells divide by mitosis to grow and repair tissue."},
    {"kind": "image", "page": 2, "image": "notes.png"},
    {"kind": "image", "page": 3, "image": "shapes.png"},
    {"kind": "text", "page": 4, "text": "Area of a circle is pi times the radius squared."},
]

# 1. INGEST — a vision model writes a description of each picture.
#    Scripted here (no key); swap in LocalVision or Gemini — same interface.
describer = GenericFakeChatModel(messages=iter([
    AIMessage("Whiteboard notes. Title: PHOTOSYNTHESIS. Below: light + water + CO2."),
    AIMessage("A diagram with a red circle on the left and a blue square on the right."),
]))
docs = []
for item in pack:
    if item["kind"] == "text":
        docs.append(Document(item["text"], metadata={"page": item["page"], "kind": "text"}))
    else:
        caption = describer.invoke([HumanMessage(content=[
            {"type": "text", "text": "Describe this study image for a search index. Copy any text exactly."},
            image_block(item["image"]),
        ])]).text
        docs.append(Document(caption,                                    # the WORDS get embedded
            metadata={"page": item["page"], "kind": "image", "image": item["image"]}))  # the PICTURE
store = InMemoryVectorStore.from_documents(docs, HashEmbeddings())

# 2. RETRIEVE — words in, words out
question = "What do plants need for photosynthesis?"
hits = store.similarity_search_with_score(question, k=2)
for d, s in hits:
    print(f"{s:.3f}", d.metadata, "|", d.page_content)


# 3. ANSWER — send the retrieved text AND the original picture to a vision model
class Inspector(GenericFakeChatModel):             # scripted: reports what it was given
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        blocks = messages[-1].content_blocks
        kinds = ", ".join(b["type"] for b in blocks)
        return ChatResult(generations=[ChatGeneration(
            message=AIMessage(f"received {len(blocks)} blocks: {kinds}"))])

content = [{"type": "text", "text":
    f"Answer from the sources. Cite pages.\nQuestion: {question}\n\n" +
    "\n".join(f"[page {d.metadata['page']}] {d.page_content}" for d, _ in hits)}]
content += [image_block(d.metadata["image"]) for d, _ in hits if d.metadata.get("image")]
print(Inspector(messages=iter([])).invoke([HumanMessage(content=content)]).text)
```

Output:

```
0.144 {'page': 2, 'kind': 'image', 'image': 'notes.png'} | Whiteboard notes. Title: PHOTOSYNTHESIS. Below: light + water + CO2.
0.000 {'page': 4, 'kind': 'text'} | Area of a circle is pi times the radius squared.
received 2 blocks: text, image
```

The top hit matches JS exactly. The second hit differs: JS returned page 1 and Python returned
page 4. Both scored 0.000. With a tie, each vector store keeps its own order. A zero score is a
"no match", not a "weak match". Exercise 4 filters these out.

### 5.8 A voice pipeline with a stopwatch

```python
# voice.py — speech in, speech out: STT → LLM → TTS, with a stopwatch on each stage
import subprocess, time, wave
import numpy as np
from transformers import pipeline


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate, channels = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.reshape(-1, channels)[:, 0].astype(np.float32) / 32768.0, rate


def say(text, out):
    subprocess.run(["pwsh", "-NoProfile", "-File", "say.ps1", "-Text", text, "-Out", out], check=True)
    with wave.open(out, "rb") as w:
        return w.getnframes() / w.getframerate()


t = time.perf_counter()
stt = pipeline("automatic-speech-recognition", model="openai/whisper-tiny.en")
llm = pipeline("text-generation", model="HuggingFaceTB/SmolLM2-135M-Instruct")
print(f"load both models: {(time.perf_counter() - t) * 1000:.0f} ms")


def voice_turn(in_file, out_file):
    times = {}
    t = time.perf_counter()
    samples, rate = read_wav(in_file)
    assert rate == 16000, f"{in_file} is {rate} Hz; Whisper needs 16000"   # see §7
    question = stt({"raw": samples, "sampling_rate": rate})["text"].strip()
    times["stt"] = round((time.perf_counter() - t) * 1000)

    t = time.perf_counter()
    out = llm([
        {"role": "system", "content": "You are StudyBuddy. Answer in one short sentence."},
        {"role": "user", "content": question},
    ], max_new_tokens=40, do_sample=False)
    answer = out[0]["generated_text"][-1]["content"]
    times["llm"] = round((time.perf_counter() - t) * 1000)

    t = time.perf_counter()
    reply_seconds = say(answer, out_file)                       # §5.6
    times["tts"] = round((time.perf_counter() - t) * 1000)
    return question, answer, times, len(samples) / rate, reply_seconds


for i in range(2):
    q, a, times, audio_in, reply_s = voice_turn("question.wav", "reply_py.wav")
    print(f"turn {i + 1}: {times} total={sum(times.values())} ms")
    if i == 0:
        print("  heard: ", q)
        print("  said:  ", a)
        print(f"  audio in {audio_in:.2f} s, reply audio {reply_s:.2f} s")

back, rate = read_wav("reply_py.wav")
print("reply_py.wav transcribed back:", stt({"raw": back, "sampling_rate": rate})["text"])
```

Output:

```
load both models: 1220 ms
turn 1: {'stt': 909, 'llm': 2262, 'tts': 684} total=3855 ms
  heard:  What is the difference between mitosis and meiosis?
  said:   Mitosis and meiosis are two types of cell division that occur in eukaryotic cells, but they differ in the number of chromosomes and the type of genetic material being replicated. Mitosis results in two genetically
  audio in 4.38 s, reply audio 16.03 s
turn 2: {'stt': 998, 'llm': 2738, 'tts': 809} total=4545 ms
reply_py.wav transcribed back:  mitosis and meiosis are two types of cell division that occur in eukaryotic cells, but they differ in the number of chromosomes and the type of genetic material being replicated.
```

Python heard the question correctly. Its 32-bit LLM was slower than the 8-bit JS one (2.3–2.7 s
against 1.2–1.3 s). Look at the last line: when transcribing the reply back, Whisper **dropped**
the cut-off fragment "Mitosis results in two genetically". A round-trip test can hide a
truncated answer, so check the text length as well.

### 5.9 Image generation

Run against a local stand-in server, like §4.9; the real provider call was *not executed*.

```python
# image_gen.py — ask an image model for a picture and save it
import base64
from pathlib import Path
from openai import OpenAI
from image_block import sniff_mime

client = OpenAI()                            # reads OPENAI_API_KEY; we used base_url → a local fake
result = client.images.generate(
    model="gpt-image-1",                     # illustrative — check your provider's current model list
    prompt="A simple labelled diagram of a plant cell, flat colours, white background",
    size="1024x1024",
    n=1,
)
data = base64.b64decode(result.data[0].b64_json)
Path("generated.png").write_bytes(data)
print("saved generated.png:", len(data), "bytes,", sniff_mime(data))
```

```
server got: POST /v1/images/generations {"model":"gpt-image-1","prompt":"A simple labelled diagram of a plant cell, flat colours, white background","n":1,"size":"1024x1024"}
saved generated.png: 3739 bytes, image/png
```

### 5.10 The JS ↔ Python translation for today

| Concept | JavaScript | Python |
|---|---|---|
| Standard image block | `{ type: "image", data, mimeType }` | `{"type": "image", "base64": ..., "mime_type": ...}` |
| Normalised view of blocks | `msg.contentBlocks` | `msg.content_blocks` |
| Old 0.3 block (`source_type`) | passed to your model **unchanged** | **converted** to v1 before your model sees it |
| `data:` prefix inside the base64 field | sent to Gemini as-is | `binascii.Error` before sending |
| Wrong MIME type | sent as-is | sent as-is |
| Read the reply text | `res.text` | `res.text` |
| Local VLM class | `AutoModelForImageTextToText` (Transformers.js) | `AutoModelForImageTextToText` (transformers) |
| Image splitting option | `processor(prompt, images, { do_image_splitting })` | `AutoProcessor.from_pretrained(..., do_image_splitting=...)` |
| Bytes → image | `RawImage.fromBlob(new Blob([buf]))` | `Image.open(io.BytesIO(raw))` |
| Read a WAV file | `wavefile` package | standard `wave` + NumPy |
| Resample to 16 kHz | `wav.toSampleRate(16000)` (built in) | needs `torchaudio` (else `ImportError`) |
| Wrong-rate audio, undeclared | wrong words, no error | wrong words (a 25–40 s loop here), no error |
| Image in a text-only chat template | base64 pasted into the prompt as text (§8 Ex 3) | `TypeError` (§8 Ex 3) |
| Run a TTS process safely | `execFileSync(cmd, [args])` | `subprocess.run([cmd, *args], check=True)` |
| Image generation result | `result.data[0].b64_json` | `result.data[0].b64_json` |

---

## 6. Under the hood

### 6.1 Why LangChain normalises content blocks

Every provider wants images in a different shape. Gemini wants `inlineData` with a
`mimeType`. OpenAI's chat format uses an `image_url` with a data URL. Anthropic wants a `source`
object with a `media_type`. Without a common shape, every model swap would mean rewriting every
message. LangChain's standard block is that common shape. Each integration's adapter converts it
into the provider's format at the last moment. You saw this happen in §4.3: two different
input spellings became one identical Gemini request.

The adapter copies your data. It doesn't check it. That's why the `data:` prefix and the
wrong MIME type went straight through in JS. Validation is your job, at the edge of your
system, where you still know where the file came from.

### 6.2 Why tiles, and why squeeze the tokens

A transformer compares every token with every other token. Doubling the tokens roughly
quadruples that work. A 512×512 tile has 1,024 patches. Sending all of them for every tile
would make images very expensive. SmolVLM merges each 4×4 group into one token, which leaves 64
per tile (§3.1). Hosted models use their own versions of the same trade-off. That is why every
provider publishes a token rule for images, and why the rules differ.

Tiling exists for the opposite reason. One 512-pixel tile is too coarse for small text. Cutting
a large image into many tiles keeps the detail, and adding one overview tile keeps the big
picture. You choose the balance with the splitting switch, the image size, or a provider's
"detail" setting.

### 6.3 Why Whisper invents words instead of failing

Whisper's decoder is a small language model. It was trained to turn sound into **likely
text**, so it always produces some. When the audio is strange (wrong sample rate, silence, music),
it produces likely-sounding nonsense. Sometimes it repeats one phrase until it hits its length
limit, like the "cool, cool, cool" run.

Defences that work: convert the sample rate before you transcribe. Skip silent audio with a
*voice activity detector* (a small model that finds where speech starts and stops). Cap the
output length. Treat very repetitive output as a failure. Check uncertain words with the user
(Exercise 5). Only the first and last of these are executed in this chapter.

### 6.4 Cascaded pipelines and speech-to-speech models

Our voice pipeline is **cascaded**: three separate models, each passing text to the next.
Every step is easy to log, test and swap, and the LLM in the middle can use RAG and tools. The
cost is time. The stages add up, and tone of voice is lost in the middle.

**Speech-to-speech** models take audio in and give audio out, with no text step in between.
They respond faster and can hear hesitation or stress. In exchange, you lose the clean text log,
grounding in your documents is harder, and testing is harder. Many products use a mix: a
cascaded pipeline that **streams** each stage, so the first words play while the rest is still
being written. *Speech-to-speech models were not executed here.*

### 6.5 Photos and voices are personal data

A photo can show a face, a name on a notebook or a home. A voice recording is personal data
too, and in some places it counts as biometric data with stricter rules. Treat uploads like
any other PII ([Day 24](../week-04-production-projects-and-interviews/day-24-reliability.md)
§3.8). Ask before you store them, keep them only as long as you need them, and tell students
which provider will see them. Captions and transcripts can hold the same personal details as
the originals, so they need the same care.

> 📚 **Sources** (read October 2026)
>
> - Dosovitskiy et al., *An Image is Worth 16x16 Words: Transformers for Image Recognition at
>   Scale*, 2020 — https://arxiv.org/abs/2010.11929
> - Radford et al., *Robust Speech Recognition via Large-Scale Weak Supervision* (Whisper),
>   2022 — https://arxiv.org/abs/2212.04356
> - Google, Gemini API "Image understanding" (image tokens, 20 MB inline limit, formats) —
>   https://ai.google.dev/gemini-api/docs/image-understanding
> - Anthropic, "Vision" (visual tokens per 28×28 patch, size limits) —
>   https://platform.claude.com/docs/en/build-with-claude/vision
> - Model cards: https://huggingface.co/HuggingFaceTB/SmolVLM-256M-Instruct ·
>   https://huggingface.co/openai/whisper-tiny.en

---

## 7. Common mistakes

### ❌ 1. A `data:` prefix inside the base64 field

```js
// ❌ a data URL is not raw base64
{ type: "image", data: `data:image/png;base64,${b64}`, mimeType: "image/png" }
// ✅ raw base64 in data; the type goes in mimeType
{ type: "image", data: b64, mimeType: "image/png" }
```

`HumanMessage` accepted the wrong form in both languages. JS then sent it to Gemini unchanged.
Python failed before sending with `binascii.Error: Invalid base64-encoded string: number of
data characters (5005) cannot be 1 more than a multiple of 4` (all measured). The data-URL form
belongs only in an `image_url` block.

### ❌ 2. Taking the MIME type from the file name

A file called `photo.png` can be a JPEG, a HEIC photo from a phone, or not an image at all.
LangChain sent a wrong `mimeType` without complaint (measured). ✅ Read the magic bytes, as
`imageBlock` / `image_block` do, and reject anything you don't recognise.

### ❌ 3. Sending full-size phone photos

A 4000×3000 photo can be many megabytes. Our random-pixel test image was **36,066,826 bytes**
as PNG, so `imageBlock` refused it. Shrunk to 1024×768 JPEG, it was **about 250 KB**
(measured; the pixels are random, so the exact size changes a little per run). ✅ Resize on upload, before base64 adds its extra third. Then check that the text
in your real images is still readable.

### ❌ 4. Paying for the same image on every turn

Chat history is resent on every call (Day 14). If a photo sits in the history, its image tokens
are paid again on every turn. ✅ Describe or transcribe the image once, keep the text in the
history, and attach the picture only when a question needs it. Some providers also offer a
file upload API, so you send a file ID instead of the bytes.

### ❌ 5. Sending an image to a text-only model

The model can't see it. In our test, a text-only model's chat template pasted the base64 into
the prompt **as text** (JS) or crashed (Python) — Exercise 3. ✅ Check the model card for image
support, and fail loudly when an image arrives at a text-only route.

### ❌ 6. Feeding audio at the wrong sample rate

44.1 kHz audio treated as 16 kHz became "You can't stop the force." in JS and a 25–40 s
"cool, cool…" loop in Python (measured). ✅ Read the rate from the file header and convert to
16 kHz first, or `assert` it like §5.8.

### ❌ 7. Reading `.content` on a multimodal reply

```js
reply.content.toUpperCase();   // ❌ TypeError: reply.content.toUpperCase is not a function
reply.text.toUpperCase();      // ✅ "A RED CIRCLE AND A BLUE SQUARE."
```

When `content` is a list of blocks, string methods fail. Python raised
`AttributeError: 'list' object has no attribute 'upper'` (both measured). This is
[Day 04](../week-01-foundations/day-04-langchain-models.md)'s warning, and multimodal models are
where it bites. ✅ Use `.text`.

### ❌ 8. Writing voice answers like text answers

A 40-token answer became 14.64 s of audio and was cut off mid-sentence (§4.8). Lists, symbols
and links read badly aloud. ✅ Give voice mode its own short system prompt, and count words
before speaking.

### ❌ 9. Building a shell command from model output

```js
execSync(`pwsh say.ps1 -Text "${answer}"`);                    // ❌ the answer can run commands
execFileSync("pwsh", ["-File", "say.ps1", "-Text", answer]);   // ✅ one argument, no shell
```

### ❌ 10. Trusting what an image says

Text in a photo is untrusted input, just like a web page. "Ignore your instructions" written on
a whiteboard is a prompt injection that never appears in your text logs. ✅ Apply the same
defences as for documents ([Day 35](day-35-ai-security.md)).

### ❌ 11. Throwing the picture away after captioning

A caption is a lossy summary. If you store only the caption, every caption mistake becomes a
permanent retrieval mistake. ✅ Store a pointer to the original (`metadata.image`) and give the
original to the answering model (§4.7).

---

## 8. Exercises

### Exercise 1 — Three spellings, one block ●○○○○

Build three `HumanMessage`s with the same image: the standard v1 block, an OpenAI-style data
URL, and the old 0.3 form with `source_type`. Print each message's normalised blocks. Predict:
are they the same? Does a URL image (`https://…`) normalise the same way?

<details>
<summary>✅ Solution</summary>

```js
import { readFileSync } from "node:fs";
import { HumanMessage } from "@langchain/core/messages";

const b64 = readFileSync("shapes.png").toString("base64");
const forms = {
  v1: { type: "image", data: b64, mimeType: "image/png" },
  dataUrl: { type: "image_url", image_url: { url: `data:image/png;base64,${b64}` } },
  legacy: { type: "image", source_type: "base64", data: b64, mime_type: "image/png" },
};
const short = (b) => Object.fromEntries(Object.entries(b).map(([k, v]) =>
  [k, typeof v === "string" && v.length > 40 ? `<${v.length} chars>` : v]));
for (const [name, block] of Object.entries(forms)) {
  const m = new HumanMessage({ content: [{ type: "text", text: "What shapes?" }, block] });
  console.log(name, "→", JSON.stringify(m.contentBlocks.map(short)[1]));
}
```

```python
import base64
from langchain_core.messages import HumanMessage

b64 = base64.b64encode(open("shapes.png", "rb").read()).decode()
forms = {
    "v1": {"type": "image", "base64": b64, "mime_type": "image/png"},
    "dataUrl": {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    "legacy": {"type": "image", "source_type": "base64", "data": b64, "mime_type": "image/png"},
    "url": {"type": "image_url", "image_url": {"url": "https://example.com/cat.png"}},
}
short = lambda b: {k: (f"<{len(v)} chars>" if isinstance(v, str) and len(v) > 40 else v)
                   for k, v in b.items()}
for name, block in forms.items():
    m = HumanMessage(content=[{"type": "text", "text": "What shapes?"}, block])
    print(name, "→", short(m.content_blocks[1]))
```

Expected output (measured):

```
JS      v1      → {"type":"image","data":"<4988 chars>","mimeType":"image/png"}
        dataUrl → {"type":"image","mimeType":"image/png","data":"<4988 chars>"}
        legacy  → {"type":"image","mimeType":"image/png","data":"<4988 chars>"}
Python  v1      → {'type': 'image', 'base64': '<4988 chars>', 'mime_type': 'image/png'}
        dataUrl → {'type': 'image', 'id': 'lc_cb5b…', 'base64': '<4988 chars>', 'mime_type': 'image/png'}
        legacy  → {'type': 'image', 'base64': '<4988 chars>', 'mime_type': 'image/png'}
        url     → {'type': 'image', 'id': 'lc_3c5a…', 'url': 'https://example.com/cat.png'}
```

All three spellings normalise to one block (key names differ by language). Python also adds a
generated `id` to blocks converted from `image_url`. A web URL becomes an image block with a
`url` key. The model must fetch it, and many local
models can't. **Why this matters:** write wrappers and middleware against the normalised view.
Then they work whatever spelling your callers use.
</details>

### Exercise 2 — What does a picture cost? ●●○○○

Using only SmolVLM's **processor** (no generation, so it's fast), count the image tokens for
blank images of 256×256, 384×256, 1024×768 and 2048×1536, with splitting off and on. Predict
first using §3.1: 64 tokens per tile.

<details>
<summary>✅ Solution</summary>

```js
// count-image-tokens.mjs — how many tokens does a picture cost? (processor only, no generation)
import { AutoProcessor, RawImage } from "@huggingface/transformers";

const processor = await AutoProcessor.from_pretrained("HuggingFaceTB/SmolVLM-256M-Instruct");
const [IMAGE_TOKEN] = processor.tokenizer.encode("<image>", { add_special_tokens: false });
const prompt = processor.apply_chat_template(
  [{ role: "user", content: [{ type: "image" }, { type: "text", text: "Describe." }] }],
  { add_generation_prompt: true });

for (const [w, h] of [[256, 256], [384, 256], [1024, 768], [2048, 1536]]) {
  const img = new RawImage(new Uint8ClampedArray(w * h * 3).fill(255), w, h, 3);   // a blank image
  const row = [];
  for (const split of [false, true]) {
    const inputs = await processor(prompt, [img], { do_image_splitting: split });
    const ids = Array.from(inputs.input_ids.data, Number);
    row.push(`split=${split}: ${ids.filter((t) => t === IMAGE_TOKEN).length}`);
  }
  console.log(`${w}x${h}`.padEnd(10), row.join("  "));
}
```

```python
# count_image_tokens.py — how many tokens does a picture cost? (processor only, no generation)
from PIL import Image
from transformers import AutoProcessor

MODEL = "HuggingFaceTB/SmolVLM-256M-Instruct"
procs = {split: AutoProcessor.from_pretrained(MODEL, do_image_splitting=split) for split in (False, True)}
image_token = procs[False].tokenizer.convert_tokens_to_ids("<image>")
prompt = procs[False].apply_chat_template(
    [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": "Describe."}]}],
    add_generation_prompt=True)

for w, h in [(256, 256), (384, 256), (1024, 768), (2048, 1536)]:
    img = Image.new("RGB", (w, h), "white")                       # a blank image
    row = []
    for split, proc in procs.items():
        ids = proc(text=prompt, images=[img], return_tensors="pt")["input_ids"][0]
        row.append(f"split={split}: {int((ids == image_token).sum())}")
    print(f"{w}x{h}".ljust(10), "  ".join(row))
```

Output (identical in both languages):

```
256x256    split=false: 64  split=true: 1088
384x256    split=false: 64  split=true: 832
1024x768   split=false: 64  split=true: 832
2048x1536  split=false: 64  split=true: 832
```

With splitting on, the processor first scales the longest side to 2,048 pixels. So 256×256
becomes 2048×2048 = 4×4 tiles + 1 overview = 17 × 64 = 1,088. The other three become 4×3 + 1 =
13 × 64 = 832. **The lesson:** token cost depends on the model's resizing rules, not on your
file size. Measure it for your model; never assume a small image is cheap. For a hosted model,
compare the `usage_metadata.input_tokens` of the same question with and without the image
([Day 34](day-34-cost-and-latency.md) builds the ledger).
</details>

### Exercise 3 — Break it six ways ●●○○○

Predict what happens, then run each one:

1. A `data:image/png;base64,` prefix inside the base64 field, sent through `ChatGoogleGenerativeAI`.
2. A PNG labelled `image/jpeg`.
3. A 4000×3000 photo-like PNG passed to `imageBlock` / `image_block`.
4. The shapes image sent to a **text-only** model (SmolLM2-135M) through its chat template.
5. A 44.1 kHz WAV passed to Whisper with no conversion.
6. `.toUpperCase()` / `.upper()` on the `.content` of a reply whose content is a list of blocks.

<details>
<summary>✅ Solution</summary>

| # | Symptom (measured) | Why |
|---|---|---|
| 1 | **JS:** sent to Google unchanged (`"data:image/png;base64,iVB…"`). **Python:** `binascii.Error: Invalid base64-encoded string: number of data characters (5005) cannot be 1 more than a multiple of 4` | LangChain doesn't validate block data. Python's integration decodes the base64 itself. |
| 2 | Sent unchanged in both languages (`mime_type: 'image/jpeg'` on PNG bytes) | The adapter copies your label. Only magic-byte sniffing catches it. |
| 3 | `big.png: 36066826 bytes is over 5242880`; after shrinking to 1024×768 JPEG: about 250 KB in both languages (249,703 bytes with sharp, 246,891 with Pillow, same input) | Random pixels don't compress, like real photos. Resize before base64. |
| 4 | **JS:** the template pasted the whole block into a 5,261-character prompt. The base64 alone was 3,864 text tokens. Reply: *"The image is a photograph of a woman wearing a black dress and a white shirt."* **Python:** `TypeError: can only concatenate str (not "list") to str` | A text-only model has no image encoder. JS's template turned the block into text; Python's template expected a string. |
| 5 | JS: *"You can't stop the force. You can't stop the force."* Python (bare array): 25–40 s of *"Yeah, cool, cool, cool…"* | Whisper assumes 16 kHz and never checks. |
| 6 | JS: `TypeError: reply.content.toUpperCase is not a function`. Python: `AttributeError: 'list' object has no attribute 'upper'`. `.text` returned `"A red circle and a blue square."` | `content` is a list of blocks; `.text` joins the text blocks (Day 04). |

Case 4 is the dangerous one in JS: no error, just a confident, invented answer that cost
thousands of tokens.

**Repro for #4 — JS**

```js
import { pipeline } from "@huggingface/transformers";
import { imageBlock } from "./image-block.mjs";

const llm = await pipeline("text-generation", "HuggingFaceTB/SmolLM2-135M-Instruct", { dtype: "q8" });
const chat = [{ role: "user", content: [
  { type: "text", text: "What shapes and colours are in this image?" },
  imageBlock("shapes.png"),
]}];
const prompt = llm.tokenizer.apply_chat_template(chat, { tokenize: false, add_generation_prompt: true });
console.log("prompt chars:", prompt.length, "| contains base64:", prompt.includes("iVBORw0K"));
const out = await llm(chat, { max_new_tokens: 30, do_sample: false });
console.log("reply:", out[0].generated_text.at(-1).content);
// prompt chars: 5261 | contains base64: true
// reply: The image is a photograph of a woman wearing a black dress and a white shirt. The woman ...
```

**Repro for #4 — Python**

```python
from transformers import pipeline
from image_block import image_block

llm = pipeline("text-generation", model="HuggingFaceTB/SmolLM2-135M-Instruct")
chat = [{"role": "user", "content": [
    {"type": "text", "text": "What shapes and colours are in this image?"},
    image_block("shapes.png"),
]}]
try:
    llm(chat, max_new_tokens=30, do_sample=False)
except TypeError as e:
    print("TypeError:", e)          # TypeError: can only concatenate str (not "list") to str
```

**Repro for #3 — shrink before sending (both languages)**

```js
import sharp from "sharp";
await sharp("big.png").resize(1024, 1024, { fit: "inside" }).jpeg({ quality: 85 }).toFile("big-small.jpg");
```

```python
from PIL import Image
img = Image.open("big.png").convert("RGB")
img.thumbnail((1024, 1024))                 # keeps the aspect ratio
img.save("big_small.jpg", "JPEG", quality=85)
```
</details>

### Exercise 4 — Multimodal RAG that knows when it doesn't know ●●●○○

In §4.7 the second hit scored 0.000 but was still returned. Ask three questions:
"What do plants need for photosynthesis?", "Which page shows a blue square?" and
"What is the capital of France?". Add a `minScore` filter (0.1). When nothing passes, skip
the model call and reply "That isn't in your notes." Attach an image only for image hits.

<details>
<summary>✅ Solution</summary>

Our first try added only the threshold. The France question still kept three pages, scoring
0.387, 0.240 and 0.136 (JS). The toy embedder counted words like "what", "is" and "the" as
matches. So the solution also skips *stop words* — very common words that carry no meaning.

```js
// changes to mm-rag.mjs
const STOP = new Set("a an and are at by do does for from in is it of on or the to what which who why how this that with".split(" "));
// inside HashEmbeddings.vec(), first line of the word loop:
//   if (STOP.has(w)) continue;

async function retrieve(question, { k = 3, minScore = 0.1 } = {}) {
  const hits = await store.similaritySearchWithScore(question, k);
  return hits.filter(([, score]) => score >= minScore);
}

function buildMessage(question, hits) {
  if (hits.length === 0) return null;                 // nothing relevant: don't call the model
  const content = [{ type: "text", text:
    `Answer from the sources. Cite pages.\nQuestion: ${question}\n\n` +
    hits.map(([d]) => `[page ${d.metadata.page}] ${d.pageContent}`).join("\n") }];
  for (const [d] of hits) if (d.metadata.image) content.push(imageBlock(d.metadata.image));
  return new HumanMessage({ content });
}

for (const q of ["What do plants need for photosynthesis?", "Which page shows a blue square?",
                 "What is the capital of France?"]) {
  const hits = await retrieve(q);
  const msg = buildMessage(q, hits);
  console.log(q);
  console.log("   kept:", hits.map(([d, s]) => `page ${d.metadata.page} (${s.toFixed(3)})`).join(", ") || "none");
  console.log("   sends:", msg ? msg.contentBlocks.map((b) => b.type).join(" + ") : "no model call — 'That isn't in your notes.'");
}
```

```python
# changes to mm_rag.py
STOP = set("a an and are at by do does for from in is it of on or the to what which who why how this that with".split())
# inside HashEmbeddings._vec(), first lines of the word loop:
#   if w in STOP:
#       continue

def retrieve(question, k=3, min_score=0.1):
    return [(d, s) for d, s in store.similarity_search_with_score(question, k=k) if s >= min_score]


def build_message(question, hits):
    if not hits:
        return None                                   # nothing relevant: don't call the model
    content = [{"type": "text", "text":
        f"Answer from the sources. Cite pages.\nQuestion: {question}\n\n" +
        "\n".join(f"[page {d.metadata['page']}] {d.page_content}" for d, _ in hits)}]
    content += [image_block(d.metadata["image"]) for d, _ in hits if d.metadata.get("image")]
    return HumanMessage(content=content)


for q in ["What do plants need for photosynthesis?", "Which page shows a blue square?",
          "What is the capital of France?"]:
    hits = retrieve(q)
    msg = build_message(q, hits)
    print(q)
    print("   kept:", ", ".join(f"page {d.metadata['page']} ({s:.3f})" for d, s in hits) or "none")
    print("   sends:", " + ".join(b["type"] for b in msg.content_blocks) if msg
          else "no model call — 'That isn't in your notes.'")
```

Output (identical in both languages):

```
What do plants need for photosynthesis?
   kept: page 2 (0.204)
   sends: text + image
Which page shows a blue square?
   kept: page 3 (0.378), page 2 (0.177)
   sends: text + image + image
What is the capital of France?
   kept: none
   sends: no model call — 'That isn't in your notes.'
```

The France question now costs nothing. The blue-square question still kept page 2 at 0.177:
two different words landed in the same hash slot (a *collision*). Real embeddings (Day 10)
avoid this, and you would tune the threshold on real questions (Day 25). **Why this design:**
every image you attach costs hundreds of tokens (§3.2), so a bad retrieval hit is expensive.
</details>

### Exercise 5 — 🎯 StudyBuddy v6.5 hears and sees ●●●●○

StudyBuddy v6.5 accepts a question as **typed text**, a **voice note** (WAV) or a **photo of
notes**. Build an `intake(input)` step that turns any of them into text before the usual
StudyBuddy chain. Requirements:

- Load each model only when its kind of input first arrives.
- Use image splitting for photos (text in photos needs detail, §3.3).
- Flag words that are *close to* a course term but not equal to it (edit distance ≤ 2). Then
  ask the student to confirm instead of answering a misheard question (§4.8).
- Report which source the text came from and how long the conversion took.

<details>
<summary>✅ Solution</summary>

```js
// studybuddy-intake.mjs — StudyBuddy v6.5: questions arrive as text, a photo, or a voice note
import { readFileSync } from "node:fs";
import wavefile from "wavefile";
import { pipeline } from "@huggingface/transformers";
import { HumanMessage } from "@langchain/core/messages";
import { imageBlock } from "./image-block.mjs";
import { LocalVision } from "./local-vision.mjs";

const COURSE_TERMS = ["mitosis", "meiosis", "photosynthesis", "chlorophyll", "osmosis"];

function editDistance(a, b) {
  const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) d[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return d[a.length][b.length];
}

// Words that are NOT course terms but are close to one: the model may have misheard or misread
function suspiciousWords(text) {
  const out = [];
  for (const w of text.toLowerCase().match(/[a-z]+/g) ?? []) {
    if (COURSE_TERMS.includes(w)) continue;
    const near = COURSE_TERMS.filter((t) => editDistance(w, t) <= 2);
    if (near.length) out.push({ heard: w, maybe: near });
  }
  return out;
}

function readWav(path) {
  const wav = new wavefile.WaveFile(readFileSync(path));
  wav.toBitDepth("32f"); wav.toSampleRate(16000);
  const s = wav.getSamples();
  return new Float32Array(Array.isArray(s) ? s[0] : s);
}

let stt, vision;                                   // load each model only when first needed
async function toText(input) {
  if (input.kind === "text") return input.text;
  if (input.kind === "audio") {
    stt ??= await pipeline("automatic-speech-recognition", "onnx-community/whisper-tiny.en", { dtype: "q8" });
    return (await stt(readWav(input.path))).text.trim();
  }
  if (input.kind === "image") {
    vision ??= new LocalVision({ split: true });   // text in photos needs the detail
    const res = await vision.invoke([new HumanMessage({ content: [
      { type: "text", text: "What text is written in this image?" }, imageBlock(input.path)] })]);
    return res.text;
  }
  throw new Error(`unknown input kind: ${input.kind}`);
}

export async function intake(input) {
  const t = performance.now();
  const text = await toText(input);
  const unsure = suspiciousWords(text);
  return {
    source: input.kind, text, ms: Math.round(performance.now() - t),
    next: unsure.length
      ? `confirm: ${unsure.map((u) => `did you mean ${u.maybe.join(" or ")} (heard "${u.heard}")?`).join(" ")}`
      : "answer",
  };
}

for (const input of [
  { kind: "text", text: "What is osmosis?" },
  { kind: "audio", path: "question.wav" },
  { kind: "image", path: "notes.png" },
]) console.log(await intake(input));
```

```python
# studybuddy_intake.py — StudyBuddy v6.5: questions arrive as text, a photo, or a voice note
import re, time, wave
import numpy as np
from transformers import pipeline
from langchain_core.messages import HumanMessage
from image_block import image_block
from local_vision import LocalVision

COURSE_TERMS = ["mitosis", "meiosis", "photosynthesis", "chlorophyll", "osmosis"]


def edit_distance(a, b):
    d = [[i] + [0] * len(b) for i in range(len(a) + 1)]
    d[0] = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
    return d[len(a)][len(b)]


def suspicious_words(text):
    """Words that are NOT course terms but are close to one: maybe misheard or misread."""
    out = []
    for w in re.findall(r"[a-z]+", text.lower()):
        if w in COURSE_TERMS:
            continue
        near = [t for t in COURSE_TERMS if edit_distance(w, t) <= 2]
        if near:
            out.append({"heard": w, "maybe": near})
    return out


def read_wav(path):
    with wave.open(path, "rb") as w:
        rate, ch = w.getframerate(), w.getnchannels()
        pcm = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return pcm.reshape(-1, ch)[:, 0].astype(np.float32) / 32768.0, rate


_models = {}                                      # load each model only when first needed

def to_text(inp):
    if inp["kind"] == "text":
        return inp["text"]
    if inp["kind"] == "audio":
        stt = _models.setdefault("stt", pipeline("automatic-speech-recognition",
                                                 model="openai/whisper-tiny.en"))
        samples, rate = read_wav(inp["path"])
        return stt({"raw": samples, "sampling_rate": rate})["text"].strip()
    if inp["kind"] == "image":
        vision = _models.setdefault("vision", LocalVision(split=True))   # text needs detail
        return vision.invoke([HumanMessage(content=[
            {"type": "text", "text": "What text is written in this image?"},
            image_block(inp["path"])])]).text
    raise ValueError(f"unknown input kind: {inp['kind']}")


def intake(inp):
    t = time.perf_counter()
    text = to_text(inp)
    unsure = suspicious_words(text)
    nxt = ("confirm: " + " ".join(
        f"did you mean {' or '.join(u['maybe'])} (heard \"{u['heard']}\")?" for u in unsure)
        if unsure else "answer")
    return {"source": inp["kind"], "text": text,
            "ms": round((time.perf_counter() - t) * 1000), "next": nxt}


for inp in [
    {"kind": "text", "text": "What is osmosis?"},
    {"kind": "audio", "path": "question.wav"},
    {"kind": "image", "path": "notes.png"},
]:
    print(intake(inp))
```

Output (measured; times include loading each model on first use):

```
JS      { source: 'text',  text: 'What is osmosis?', ms: 0, next: 'answer' }
        { source: 'audio', text: 'What is the difference between mitosis and myosis?', ms: 2051,
          next: 'confirm: did you mean mitosis or meiosis (heard "myosis")?' }
        { source: 'image', text: 'Photosynthesis is light + water + CO2', ms: 15026, next: 'answer' }
Python  {'source': 'text',  'text': 'What is osmosis?', 'ms': 0, 'next': 'answer'}
        {'source': 'audio', 'text': 'What is the difference between mitosis and meiosis?', 'ms': 1940, 'next': 'answer'}
        {'source': 'image', 'text': 'PHOTOSYNTHESIS light + water + CO2', 'ms': 18087, 'next': 'answer'}
```

The JS run caught its own mishearing. "myosis" is distance 2 from both "mitosis" and
"meiosis", so it asks the student instead of guessing. The Python run heard correctly and went
straight on. **Why this design:** a cheap check on the converted text catches errors before an
expensive and confident wrong answer. The `next: "answer"` text flows into the StudyBuddy chain
you already have, so the rest of the system doesn't change. Lazy loading keeps start-up fast for
students who only type. **StudyBuddy v6.5: questions by photo or voice, with a "did you mean"
check.**
</details>

---

## 9. Interview questions

### Basic

**Q1. How does a vision-language model "see" an image?**

It cuts the image into small square patches (16×16 pixels in the original ViT paper and in
SmolVLM). A vision encoder turns them
into vectors, and these are compressed into a few dozen to a few thousand **image tokens**. The
language model reads those tokens alongside the text tokens. In SmolVLM, one 512×512 tile
became 64 tokens after merging 4×4 groups of patches (measured).

---

**Q2. How do you send an image to a chat model in LangChain?**

As a content block in a `HumanMessage` list: text block plus image block. The standard block is
`{type: "image", data, mimeType}` in JS and `{"type": "image", "base64", "mime_type"}` in
Python. The provider integration converts it into the provider's own format. Read
`contentBlocks` / `content_blocks` for a normalised view.

---

**Q3. Why does an image cost more than the question about it?**

Because it becomes many tokens. One provider documents 258 tokens per 768×768 tile; another
charges one token per 28×28-pixel patch, so a 1000×1000 photo is 1,296 tokens. A 6-word
question is a few tokens. And base64 makes the request about 33 % bigger than the file.

---

**Q4. What is a sample rate, and why does Whisper care?**

The number of audio measurements per second. Whisper was trained on 16 kHz audio and never
checks the rate. 44.1 kHz audio fed as if it were 16 kHz sounds slowed down to the model. It
produced invented sentences in our test, with no error.

---

### Intermediate

**Q5. Native multimodal or convert-to-text first — how do you choose?**

Convert first (caption, OCR, transcribe) when you need search, logs, any text model, and a
one-time cost. Send the image natively when details like layout, arrows or colour matter for
this one question. Most systems do both: captions to find the image, then the original to
answer.

---

**Q6. Design RAG over lecture slides that contain diagrams.**

At ingest, a VLM writes a caption for each figure ("copy any text exactly"). Store it as a
`Document` with metadata pointing at the image file and page. Embed captions and text chunks in
the same store. At query time, filter by a score threshold, then send the retrieved text plus
the original images to a VLM. Alternatives: multimodal embeddings (search images directly) or
page screenshots. Trade-off: captioning is cheap at query time but lossy.

---

**Q7. Why validate images yourself when the provider will reject bad ones?**

Because LangChain passes bad data through silently. In our test, a wrong MIME type and a
`data:` prefix both reached the request body in JS. The provider's error comes late, costs a
round trip and is often vague. Checking magic bytes and size at upload gives a clear error, and
lets you resize before paying for tokens.

---

**Q8. Your voice tutor takes 3–4 seconds to start speaking. Where does the time go, and how do you cut it?**

Measure each stage. In ours, STT was about 1 s, the LLM 1.2–2.7 s and TTS 0.6–0.8 s on a CPU.
Cut it by streaming: transcribe while the user speaks, stream LLM tokens, and start TTS on the
first sentence. Also keep answers short, use smaller or quantised models, and consider
speech-to-speech models if text logs matter less.

---

**Q9. A reply's `.content.toUpperCase()` crashes in production but not in tests. Why?**

The production model returns `content` as a list of blocks (text plus other parts); the test
model returned a string. `.text` always joins the text blocks into a string (Day 04). Multimodal
and reasoning models make the list form common.

---

**Q10. What does image resolution trade off?**

Detail against tokens and time. With SmolVLM, splitting raised the tokens from 83 to 613 and the
time 6–10×. In return, the model read text it otherwise missed or invented. Pick the smallest
size that keeps your real images readable, and test on them.

---

### Advanced

**Q11. Design StudyBuddy's voice mode for 10,000 students.**

A cascaded, streaming pipeline: voice activity detection, streaming STT, the existing RAG
agent with a "voice" system prompt (short, no lists), and streaming TTS that starts on the
first sentence. Confirm low-confidence course terms. Keep transcripts as the record. Budget each
stage with p95 latencies (Day 34), give TTS a fallback to text (Day 24), and treat audio as
personal data with a short retention period.

---

**Q12. How do you test a multimodal feature automatically?**

Use golden inputs drawn with code (exact pixels, known text) and synthesised audio (byte-identical
on each run in our test). Assert on the converted text: OCR exact match, word error rate for STT.
Round-trip TTS → STT to check spoken output, plus a length check, because Whisper dropped a
cut-off fragment in our run. Use scripted models to test the message plumbing without keys.

---

**Q13. How can an image attack an agent?**

Text inside the image can carry instructions ("ignore previous instructions…"). It is invisible
in text logs and reaches the model like any other content. The defences are the same as for
documents (Day 35). Give the agent that reads uploads the least privilege and no dangerous
tools. Require human approval for actions. Treat image-derived text as data, not instructions.

---

**Q14. When would you use image generation in an education product, and when not?**

Use it for decoration: cover images, illustrative cartoons, varied practice prompts. Don't use
it for facts — labelled diagrams, maps, charts — because generated labels and structures can be
wrong. It also costs more per call, raises copyright and safety questions, and needs labelling
as AI-generated.

---

## 10. Recap

### What you learned

- ✅ Images become **patches, then image tokens**; SmolVLM uses 64 per 512-pixel tile
- ✅ Image tokens **cost money** on every call; each provider has its own counting rule
- ✅ **Resolution is a trade-off**: splitting cost 7× the tokens but read text the small model missed
- ✅ LangChain's **standard image block** normalises three spellings; JS and Python key names differ
- ✅ LangChain **doesn't validate** image data — sniff magic bytes, cap size, resize
- ✅ A **local VLM** can be wrapped as a LangChain chat model by reading `contentBlocks`
- ✅ Whisper needs **16 kHz** audio; wrong rates give confident nonsense, not errors
- ✅ **TTS** answers need short prompts; call external processes without a shell
- ✅ **Multimodal RAG**: embed captions, keep a pointer to the picture, answer with the original
- ✅ **Voice pipelines** add up stage by stage, and errors flow downstream — confirm uncertain words
- ✅ **Image generation** is for illustration, never for facts

### One-glance summary

```
   photo ─► sniff + resize ─► image block ─► VLM ───────────────► answer
                                   └─► caption ─► vector store ─┘ (RAG: words find, picture answers)
   voice ─► 16 kHz ─► Whisper ─► "did you mean?" ─► LLM ─► short reply ─► TTS ─► 🔊
   always: measure tokens and seconds · treat image/audio text as untrusted · use .text
```

### Tomorrow

**[Day 34 — Cost & latency](day-34-cost-and-latency.md)**: today a single photo cost hundreds
of tokens and a voice turn took three to four seconds. Tomorrow you find out where StudyBuddy's
money and waiting time really go. You build a cost ledger, then remove waste with caching,
routing, batching and a budget guard.

### Quick self-check

1. A student's 384×256 diagram costs 832 image tokens in SmolVLM with splitting on, but 64 with
   it off. Why is the small image so expensive with splitting, and when is that worth paying?
2. Your JS voice pipeline answers questions about "myosis". Name two places in the pipeline
   where you could have caught it.
3. Your multimodal RAG returns a diagram for "What is the capital of France?". Name two fixes.

<details>
<summary>Answers</summary>

1. With splitting on, SmolVLM first enlarges the image so its longest side is 2,048 pixels. It
   then cuts that into 12 tiles of 512 pixels plus one overview tile: 13 × 64 = 832 tokens. It's
   worth it when the image holds small text (splitting read "PHOTOSYNTHESIS" in our test) and
   wasteful for simple pictures, which the 64-token version described correctly.
2. At STT: use a stronger or higher-precision model (Python's 32-bit Whisper heard "meiosis").
   After STT: compare words with the course vocabulary and ask "did you mean meiosis or
   mitosis?" (Exercise 5). The LLM can't fix it later — it explains whatever it was given.
3. Add a score threshold and skip the model call when nothing passes (Exercise 4). Improve the
   embeddings: drop stop words in the toy embedder, or use a real embedding model (Day 10). Then
   tune the threshold on real questions (Day 25).
</details>

---

<div align="center">

**[← Day 32 — Dataset engineering](day-32-dataset-engineering.md)** · **[Week 5 index](README.md)** · **[Day 34 — Cost & latency →](day-34-cost-and-latency.md)**

</div>
