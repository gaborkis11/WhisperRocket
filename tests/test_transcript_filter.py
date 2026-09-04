#!/usr/bin/env python3
"""
Tests for transcript_filter.py - what Whisper writes on silence is dropped.

    python3 tests/test_transcript_filter.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from transcript_filter import filter_transcript, is_hallucination  # noqa: E402

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


# real cases from the history
t = ("Szia, Fruzsi! Most beszéltem Canival. Amúgy minden ok, jó volt a megbeszélés az irodában. "
     "Feliratot készítette Amara.org közössége")
out = filter_transcript(t)
check("subtitle credit at the end is dropped", out.endswith("az irodában.") and "Amara" not in out, out)

t = "Nekem korán indult a nap. Feliratok az Amara.org közösségétől"
check("'Feliratok az Amara.org közösségétől' is dropped", filter_transcript(t) == "Nekem korán indult a nap.",
      filter_transcript(t))

t = "Ha tetszett, kapcsold be az angol feliratot. Köszönöm a figyelmet."
check("nothing real left -> empty string", filter_transcript(t) == "", repr(filter_transcript(t)))

# the word itself is fine
t = "A feliratot tedd a gomb alá, és a másik felirat maradjon."
check("'felirat' as a normal word is untouched", filter_transcript(t) == t, filter_transcript(t))

# accents and case do not matter
check("accent-insensitive match", is_hallucination("FELIRATOT KÉSZÍTETTE Amara"))

# stage directions
t = "Szia! [zene] Ez itt a lényeg (nevetés) és kész."
check("bracketed stage directions are dropped", filter_transcript(t) == "Szia! Ez itt a lényeg és kész.",
      filter_transcript(t))

# repetition loops
t = "hogy azoknak azoknak azoknak azoknak azoknak azoknak az hogy a lába se éri a földet"
check("a word repeated three or more times collapses to one",
      filter_transcript(t) == "hogy azoknak az hogy a lába se éri a földet", filter_transcript(t))
check("a double word is left for the cleanup", filter_transcript("ezt ezt holnap") == "ezt ezt holnap")
check("repetition with commas collapses too", filter_transcript("na, na, na, na, jó") == "na, jó")
t = ("amik el vannak mentve stílus profil promptok fogalmazómód meg minden ilyen dolgokat "
     "amik el vannak mentve stílus profil promptok fogalmazómód meg minden ilyen dolgokat "
     "amik el vannak mentve stílus profil promptok fogalmazómód meg minden ilyen dolgokat azt ugye oda menti")
check("a phrase looped verbatim collapses to one",
      filter_transcript(t) == "amik el vannak mentve stílus profil promptok fogalmazómód meg minden ilyen dolgokat azt ugye oda menti",
      filter_transcript(t))
t = ("hogy ezt a szótárt is meg kellene nézni meg kellene nézni meg kellene nézni "
     "meg kellene nézni meg kellene nézni meg kellene ez csak úgy szintén")
check("a short phrase looped five times collapses to one, even with a partial tail",
      filter_transcript(t) == "hogy ezt a szótárt is meg kellene nézni meg kellene ez csak úgy szintén",
      filter_transcript(t))
t = "na jó tehát na jó tehát na jó tehát akkor na jó tehát na jó tehát na jó tehát akkor mehet"
check("nested loops collapse all the way",
      filter_transcript(t) == "na jó tehát akkor mehet", filter_transcript(t))
check("a two-word phrase said twice is left alone (could be emphasis)",
      filter_transcript("nagyon jó nagyon jó lett") == "nagyon jó nagyon jó lett")

# untouched ordinary text
t = "Oké, most éppen látom az ikont. Viszont ha ráklikkelek, hogy megnyíljon, akkor csak felugrik."
check("ordinary text passes through unchanged", filter_transcript(t) == t)
check("empty input stays empty", filter_transcript("") == "")

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
