"""Measure how easy the prose in the day files is to read.

    python tools/readability.py .                  # table for every day file
    python tools/readability.py FILE [FILE ...]    # scores + every sentence over 30 words

Code blocks, tables, headings and HTML lines are removed first, and inline code counts as one
short word, so the score reflects the explanations, not the code. The syllable counter is an
approximation: use the numbers to rank days and to compare before/after an edit, not as exact
values. House target: Flesch >= 60 and as few sentences over 30 words as possible.
"""
import glob
import io
import os
import re
import sys

LONG = 30


def syllables(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 0
    if len(w) <= 3:
        return 1
    w = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", w)
    w = re.sub(r"^y", "", w)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", w)))


def prose(text):
    # fences only at line start, so an inline span like ```json``` can't open a "block"
    text = re.sub(r"^\s*```[^\n]*\n.*?^\s*```[^\n]*$", "\n\n", text, flags=re.M | re.S)
    paras, cur = [], []

    def flush():
        if cur:
            p = " ".join(cur)
            paras.append(p if p[-1] in ".!?" else p + ".")   # a bullet/paragraph ends a sentence
            cur.clear()

    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("|", "#", "<", "---")):
            flush()
            continue
        s = re.sub(r"^>\s*", "", s)                           # blockquote marker
        if re.match(r"^([-*]|\d+\.)\s+", s):                  # a list item starts a new sentence
            flush()
            s = re.sub(r"^([-*]|\d+\.)\s+", "", s)
        s = re.sub(r"`[^`]*`", "X", s)
        s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
        s = re.sub(r"[*_]", "", s).strip()
        if s:
            cur.append(s)
    flush()
    return " ".join(paras)


def measure(path):
    t = prose(io.open(path, encoding="utf-8").read())
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t) if len(s.split()) >= 3]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", t)
    if not sents or not words:
        return None
    asl = len(words) / len(sents)
    asw = sum(syllables(w) for w in words) / len(words)
    return {
        "words": len(words),
        "asl": asl,
        "flesch": 206.835 - 1.015 * asl - 84.6 * asw,
        "grade": 0.39 * asl + 11.8 * asw - 15.59,
        "long": [s for s in sents if len(s.split()) > LONG],
        "sents": len(sents),
    }


def main(args):
    if len(args) == 1 and os.path.isdir(args[0]):
        files = sorted(glob.glob(os.path.join(args[0], "week-0*", "day-*.md")))
        show_long = False
    else:
        files, show_long = args, True
    print(f"{'file':40} {'words':>6} {'sent':>5} {'flesch':>6} {'grade':>5} {'>30w':>5}")
    scores = []
    for f in files:
        m = measure(f)
        if not m:
            continue
        scores.append(m["flesch"])
        print(f"{os.path.basename(f)[:40]:40} {m['words']:6} {m['asl']:5.1f} {m['flesch']:6.0f} "
              f"{m['grade']:5.1f} {len(m['long']):5}")
        if show_long:
            for s in m["long"]:
                print(f"    [{len(s.split())}w] {s[:300]}")
    if len(scores) > 1:
        print(f"\nmean flesch {sum(scores) / len(scores):.0f} over {len(scores)} files")


if __name__ == "__main__":
    main(sys.argv[1:] or ["."])
