"""Add the previous / week index / next footer to any day file that lacks one.

    python tools/add_footers.py [repo-root]          # add missing footers
    python tools/add_footers.py [repo-root] --check  # only list files without one

The course order is the folder order (week-00 … week-06), then the file order inside each folder
(day-00a, day-00b, …, day-29, …). Existing footers are never touched. The short name in a link
is the day's H1 title up to its first ":" (e.g. "Day 13 — Advanced RAG").
"""
import glob
import io
import os
import re
import sys

ROOT = next((a for a in sys.argv[1:] if not a.startswith("--")), ".")
CHECK = "--check" in sys.argv


def info(path):
    text = io.open(path, encoding="utf-8").read()
    m = re.search(r"^# Day ([0-9]+[A-C]?) — (.+)$", text, re.M)
    label, title = m.group(1), m.group(2)
    short = re.split(r":| · ", title)[0].strip()
    return {"path": path, "text": text, "label": label, "short": short,
            "week": int(re.search(r"week-(\d+)", path).group(1))}


def has_footer(text):
    return 'div align="center"' in text[-1500:]


def link(src, dst, arrow_left):
    rel = os.path.relpath(dst["path"], os.path.dirname(src["path"])).replace(os.sep, "/")
    name = f"Day {dst['label']} — {dst['short']}"
    return f"**[← {name}]({rel})**" if arrow_left else f"**[{name} →]({rel})**"


def main():
    days = [info(p) for p in sorted(glob.glob(os.path.join(ROOT, "week-0*", "day-*.md")))]
    missing = 0
    for i, d in enumerate(days):
        if has_footer(d["text"]):
            continue
        missing += 1
        if CHECK:
            print("no footer:", os.path.relpath(d["path"], ROOT))
            continue
        prev = link(d, days[i - 1], True) if i else "**[← Course home](../README.md)**"
        nxt = (link(d, days[i + 1], False) if i + 1 < len(days)
               else "**[Course home →](../README.md)**")
        footer = (f'\n\n---\n\n<div align="center">\n\n{prev} · **[Week {d["week"]} index](README.md)**'
                  f' · {nxt}\n\n</div>\n')
        io.open(d["path"], "w", encoding="utf-8", newline="").write(d["text"].rstrip() + footer)
        print("added footer:", os.path.relpath(d["path"], ROOT))
    print(f"{missing} file(s) {'without' if CHECK else 'fixed, previously without'} a footer")


if __name__ == "__main__":
    main()
