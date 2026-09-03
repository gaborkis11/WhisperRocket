#!/usr/bin/env python3
"""
Tests for the AI cleanup guard (ai_guard.py).

The guard rejects a cleanup that reworded, softened or padded the transcript,
and hands the raw text back instead. A false positive there throws away good
output, which is what happened on 2026-09-03: the model corrected "susit" to
"sushit" and the substring test for "shit" rejected the whole message.

Standard library only.

    python3 tests/test_ai_guard.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import ai_guard  # noqa: E402

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")


def verdict(raw, out):
    return ai_guard.check(raw, out, "transcript")


# --- profanity added: word-start match, not substring ------------------------
r = verdict("valószínűleg eszek egy kis susit, mert mindjárt éhen halok",
            "Valószínűleg eszek egy kis sushit, mert mindjárt éhen halok.")
check("'sushit' is not 'shit': a spelling fix passes", r.ok, str(r.failures))

r = verdict("ez jó lett", "Ez kibaszott jó lett.")
check("a swear word the speaker never said is still caught behind a verbal prefix",
      not r.ok and any(f.startswith("profanity_added") for f in r.failures), str(r.failures))

r = verdict("ez jó lett", "Ez fasza lett.")
check("a bare stem added is caught", not r.ok, str(r.failures))

r = verdict("ez kibaszott jó lett bazdmeg", "Ez kibaszott jó lett, bazdmeg.")
check("swearing kept on both sides passes", r.ok, str(r.failures))

# --- profanity softened: still generous --------------------------------------
r = verdict("ez kibaszott jó lett", "Ez nagyon jó lett.")
check("softening is caught", not r.ok and any(f.startswith("profanity_softened") for f in r.failures),
      str(r.failures))

# --- the basic checks still hold ---------------------------------------------
r = verdict("figyelj a gond az hogy nem indul el a program",
            "Figyelj, a gond az, hogy nem indul el a program.")
check("punctuation-only cleanup passes", r.ok, str(r.failures))

r = verdict("figyelj a gond az hogy nem indul el a program", "Rendben.")
check("a reply instead of a transcript fails on length", not r.ok, str(r.failures))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
