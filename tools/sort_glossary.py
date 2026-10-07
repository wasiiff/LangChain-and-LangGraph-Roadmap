"""Sort every glossary section alphabetically (case-insensitive), preserving entries verbatim."""
import io
import re
import sys

path = sys.argv[1]
lines = io.open(path, encoding="utf-8").read().split("\n")

heads = [(i, m.group(1)) for i, l in enumerate(lines) if (m := re.match(r"^## ([A-Z])\s*$", l))]
before = sum(1 for l in lines if l.startswith("**"))

for idx in range(len(heads) - 1, -1, -1):
    start = heads[idx][0]
    end = heads[idx + 1][0] if idx + 1 < len(heads) else len(lines)
    block = lines[start + 1:end]

    entries, current, trailer = [], None, []
    for l in block:
        if l.startswith("**"):
            current = [l]
            entries.append(current)
        elif l.strip() == "---":
            trailer = ["---"]
            current = None
        elif current is not None and l.strip():
            current.append(l)

    if not entries:
        continue
    entries.sort(key=lambda e: re.match(r"^\*\*(.+?)\*\*", e[0]).group(1).lower())

    rebuilt = [""]
    for e in entries:
        rebuilt.extend(e)
        rebuilt.append("")
    if trailer:
        rebuilt.extend(trailer + [""])
    lines[start + 1:end] = rebuilt

after = sum(1 for l in lines if l.startswith("**"))
assert before == after, f"entry count changed: {before} -> {after}"
io.open(path, "w", encoding="utf-8").write("\n".join(lines))
print(f"sorted; entries unchanged at {after}")
