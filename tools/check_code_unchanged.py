"""Prove that a prose edit did not touch any code.

    python tools/check_code_unchanged.py FILE [FILE ...]

Compares each file with its version in the git index (`git show :FILE`, i.e. the last
committed or staged copy) and checks that:

  1. every fenced code block in the old file still exists, character for character, and in
     the same order (new blocks may be added between them);
  2. every `inline code` span in the old file still appears at least as many times.

Exit code 1 if anything was removed or changed. Added code is listed for review, not failed:
new sections may legitimately add verified code.
"""
import collections
import io
import re
import subprocess
import sys

FENCE = re.compile(r"^```[^\n]*\n.*?^```[^\n]*$", re.M | re.S)
INLINE = re.compile(r"`[^`\n]+`")


def parts(text):
    blocks = FENCE.findall(text)
    rest = FENCE.sub("", text)
    return blocks, collections.Counter(INLINE.findall(rest))


def check(path):
    try:
        old = subprocess.run(["git", "show", f":{path}"], capture_output=True, text=True,
                             encoding="utf-8", check=True).stdout
    except subprocess.CalledProcessError:
        print(f"{path}: not in git index — nothing to compare (new file)")
        return True
    new = io.open(path, encoding="utf-8").read()
    ob, oi = parts(old)
    nb, ni = parts(new)

    ok = True
    j = 0                                   # ordered subsequence match of old blocks in new
    missing = []
    for b in ob:
        k = j
        while k < len(nb) and nb[k] != b:
            k += 1
        if k == len(nb):
            missing.append(b)
        else:
            j = k + 1
    added_blocks = len(nb) - (len(ob) - len(missing))
    if missing:
        ok = False
        print(f"{path}: {len(missing)} code block(s) REMOVED or CHANGED:")
        for b in missing:
            print("    " + b.splitlines()[0] + " | " + (b.splitlines()[1][:80] if len(b.splitlines()) > 1 else ""))
    lost = oi - ni
    if lost:
        ok = False
        print(f"{path}: inline code REMOVED or CHANGED: {dict(lost)}")
    gained = ni - oi
    status = "OK — all code unchanged" if ok else "FAILED"
    print(f"{path}: {status} · {len(ob)} old blocks kept · {added_blocks} block(s) added · "
          f"{sum(gained.values())} inline span(s) added")
    return ok


if __name__ == "__main__":
    results = [check(p.replace("\\", "/")) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
