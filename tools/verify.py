"""Full-repo verification: links, day structure, language parity, exercise solutions, stats."""
import glob
import io
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
problems = []


def read(p):
    return io.open(p, encoding="utf-8").read()


# ── 1. links ────────────────────────────────────────────────────────────────
files = subprocess.run(
    ["git", "-C", ROOT, "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
    capture_output=True, text=True, check=True).stdout.split()
link = re.compile(r"\]\(((?!https?:|mailto:|#)[^)#\s]+\.md)(#[^)]*)?\)")
# Fenced blocks are skipped: the KB quotes example markdown whose links aren't real here.
fence = re.compile(r"^```[^\n]*\n.*?^```[^\n]*$", re.M | re.S)
broken = 0
for rel in files:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        continue
    for m in link.finditer(fence.sub("", read(path))):
        target = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
        if not os.path.exists(target):
            problems.append(f"BROKEN LINK {rel} -> {m.group(1)}")
            broken += 1

# ── 2. day files ────────────────────────────────────────────────────────────
days = sorted(glob.glob(os.path.join(ROOT, "week-0*", "day-*.md")))
total_lines = 0
rows = []
for path in days:
    text = read(path)
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    num = int(re.search(r"day-(\d+)", os.path.basename(path)).group(1))
    lines = text.count("\n")
    total_lines += lines

    fences = len(re.findall(r"^```", text, re.M))
    if fences % 2:
        problems.append(f"ODD FENCE COUNT {rel} ({fences})")
    if text.count("<details>") != text.count("</details>"):
        problems.append(f"UNBALANCED <details> {rel}")

    required = [rf"^## {n}\. " for n in range(1, 11)]
    missing = [r for r in required if not re.search(r, text, re.M)]
    if missing:
        problems.append(f"MISSING SECTIONS {rel}: {missing}")

    js = len(re.findall(r"^```(js|javascript|ts|tsx)\b", text, re.M))
    py = len(re.findall(r"^```(python|py)\b", text, re.M))
    if js == 0 or py == 0:
        problems.append(f"LANGUAGE GAP {rel}: js={js} py={py}")

    # exercises: each solution block should contain both languages
    ex_blocks = re.split(r"^### Exercise ", text, flags=re.M)[1:]
    gaps = []
    for i, block in enumerate(ex_blocks, 1):
        sol = block.split("</details>")[0]
        has_js = re.search(r"^```(js|javascript|ts)\b", sol, re.M)
        has_py = re.search(r"^```(python|py)\b", sol, re.M)
        # analysis-only exercises legitimately have no code at all
        if (has_js and not has_py) or (has_py and not has_js):
            gaps.append(f"E{i}:{'no-PY' if has_js else 'no-JS'}")
    interview = len(re.findall(r"<summary><b>Q", text)) + len(re.findall(r"^\*\*Q\d+\.", text, re.M))
    rows.append((num, lines, js, py, len(ex_blocks), gaps, interview))

print(f"{'day':>4} {'lines':>6} {'js':>4} {'py':>4} {'ex':>3} {'Q':>3}  parity")
for num, lines, js, py, ex, gaps, q in rows:
    print(f"{num:>4} {lines:>6} {js:>4} {py:>4} {ex:>3} {q:>3}  {' '.join(gaps) if gaps else 'ok'}")

# ── 3. repo stats ───────────────────────────────────────────────────────────
all_md = [os.path.join(ROOT, f) for f in files if os.path.exists(os.path.join(ROOT, f))]
repo_lines = sum(read(p).count("\n") for p in all_md)
print(f"\nfiles: {len(all_md)} markdown · day files: {len(days)} · day lines: {total_lines:,} · repo lines: {repo_lines:,}")
print(f"interview questions in day files: {sum(r[6] for r in rows)}")
print(f"broken links: {broken}")

# ── 4. README calendar completeness ─────────────────────────────────────────
readme = read(os.path.join(ROOT, "README.md"))
if "*coming next*" in readme:
    problems.append("README still has '*coming next*' rows")
linked_days = len(re.findall(r"\[→\]\(week-0", readme))
if linked_days != 28:
    problems.append(f"README links {linked_days} days, expected 28")

print("\n" + ("PROBLEMS:" if problems else "no problems found"))
for p in problems:
    print(" -", p)
