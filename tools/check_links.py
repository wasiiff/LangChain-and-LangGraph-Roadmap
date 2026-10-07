"""Check every relative markdown link in the repo.

    python tools/check_links.py [repo-root]

Covers the files git tracks plus untracked ones git would track (so a new day file is
checked before it is committed, and anything .gitignore'd is skipped). Anchors are not
resolved — only the file part. Exits 1 if anything is broken.
"""
import io
import os
import re
import subprocess
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
LINK = re.compile(r"\]\(((?!https?:|mailto:|#)[^)#\s]+\.md)(#[^)]*)?\)")
# Fenced blocks are skipped: the KB quotes example markdown whose links aren't real here.
FENCE = re.compile(r"^```[^\n]*\n.*?^```[^\n]*$", re.M | re.S)

files = subprocess.run(
    ["git", "-C", ROOT, "ls-files", "--cached", "--others", "--exclude-standard", "*.md"],
    capture_output=True, text=True, check=True).stdout.split()

broken, checked = [], 0
for rel in files:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):          # staged deletion
        continue
    text = FENCE.sub("", io.open(path, encoding="utf-8").read())
    for m in LINK.finditer(text):
        checked += 1
        target = os.path.normpath(os.path.join(os.path.dirname(path), m.group(1)))
        if not os.path.exists(target):
            broken.append(f"{rel} -> {m.group(1)}")

print(f"{len(files)} markdown files · {checked} relative links · {len(broken)} broken")
for b in broken:
    print(" BROKEN", b)
sys.exit(1 if broken else 0)
