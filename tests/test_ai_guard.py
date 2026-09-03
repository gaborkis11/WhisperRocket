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

# --- novelty: a reply instead of a transcript ----------------------------------
r = verdict("most itt vagy hallasz?", "Igen, itt vagyok, hallak.")
check("an answer to a short question is caught as invented",
      not r.ok and any(f.startswith("invented") for f in r.failures), str(r.failures))
r = verdict("veled most amúgy mi történik éppen",
            "Éppen csak transzkriptumokat tisztítok, semmi más nem történik.")
check("an answer to a longer question is caught as invented", not r.ok, str(r.failures))
r = verdict("én vittem iskolába milánt úgyhogy már hat óra tizenötkor keltem aztán dolgoztam otthon",
            "Én vittem iskolába Milánt, úgyhogy már 6:15-kor keltem. Aztán dolgoztam otthon.")
check("digits and punctuation are not novelty", r.ok, str(r.failures))
r = ai_guard.check("most beszéltem csanival és arra gondoltunk hogy te is jöhetnél",
                   "Most beszéltem Canival, és arra gondoltunk, hogy te is jöhetnél.",
                   "transcript", allowed_terms=["Cani"])
check("a dictionary term resolved by the model is allowed", r.ok, str(r.failures))

# --- entities survive ------------------------------------------------------------
r = verdict("küldd el a jelentést a gabor@example.com címre és nézd meg a https://example.com/x oldalt 2026-ban",
            "Küldd el a jelentést a címre, és nézd meg az oldalt 2026-ban.")
check("a lost e-mail address and URL are caught",
      not r.ok and any(f.startswith("entity_lost") for f in r.failures), str(r.failures))
r = verdict("hívj fel a 06301234567 számon", "Hívj fel a 06301234567 számon.")
check("a kept phone number passes", r.ok, str(r.failures))

# --- word order: soft failure ----------------------------------------------------
r = verdict("figyelj bazdmeg a zsani meg a csani is ott lesz a meccsen a csapattal",
            "Bazdmeg, figyelj, a Zsani meg a Csani is ott lesz a meccsen a csapattal.")
check("two content words swapped is reported", not r.ok and any(f.startswith("reordered") for f in r.failures),
      str(r.failures))
check("a reordering alone is a soft failure", r.soft, str(r.failures))
r = verdict("most itt vagy hallasz?", "Igen, itt vagyok, hallak.")
check("an invented reply is never soft", not r.soft, str(r.failures))
r = verdict("na most több hibát is találtam igazából majd nullára eltelepítem csak egy dolog az eszembe jutott",
            "Na most több hibát is találtam, igazából majd nullára eltelepítem. Csak egy dolog az eszembe jutott.")
check("deleting filler and splitting sentences is not a reorder", r.ok, str(r.failures))
check("reordered_words counts the swap", ai_guard.reordered_words("figyelj bazdmeg ottlesz zsani", "bazdmeg figyelj ottlesz zsani") == 1)

# --- packaging -------------------------------------------------------------------
check("echoed transcript tags are stripped",
      ai_guard.strip_wrapper("<TRANSCRIPT>\nSzia! Jövök.\n</TRANSCRIPT>") == "Szia! Jövök.")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
