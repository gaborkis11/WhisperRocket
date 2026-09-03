#!/usr/bin/env python3
"""
Tests for sentence_splitter.py - the two-comma rule applied in code.

    python3 tests/test_sentence_splitter.py
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from sentence_splitter import split_long_sentences, split_sentence  # noqa: E402

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


def words_only(text):
    return "".join(ch for ch in text.lower() if ch.isalnum())


# --- sentences within the limit are untouched --------------------------------
s = "Oké, most tök jó lett, már működik."
check("two commas: unchanged", split_sentence(s) == s)
check("no commas: unchanged", split_sentence("Most kocsit mosok.") == "Most kocsit mosok.")

# --- the speaker's own seven-comma sentence ----------------------------------
seven = ("Oké, most éppen látom az ikont, viszont ha ráklikkelek, hogy megnyíljon, akkor "
         "csak felugrik egy pillanatra, és nem ott, ahol van a system tray és alatta, hanem "
         "a képernyő bal alsó részében megugrik.")
out = split_sentence(seven)
sentences = [x for x in out.replace("!", ".").split(". ") if x]
check("seven commas become several sentences", len(sentences) >= 3, out)
check("no sentence keeps more than two commas",
      all(x.count(",") <= 2 for x in sentences), out)
check("the words are exactly the same, in the same order",
      words_only(out) == words_only(seven), out)
check("the comma before 'hogy' stays", ", hogy megnyíljon" in out, out)
check("a new sentence starts with a capital after the cut",
      ". Viszont" in out or ". És" in out or ". Hanem" in out, out)

# --- grammar-owned commas are never cut ---------------------------------------
sub = "Azt mondta, hogy jön, mert kell neki, ami ott van, aki tudja, ha lehet."
check("subordinators keep their comma (nothing to cut here)",
      split_sentence(sub) == sub, split_sentence(sub))

corr = "De amúgy meg úgy vagyok arra, hogy ha csináljuk, úgy csináljuk meg, hogy tényleg jól működik."
check("'ha ..., úgy ...' correlative is not cut", "csináljuk, úgy csináljuk" in split_sentence(corr),
      split_sentence(corr))

ami = ("De ami az igazán legnehezebb volt, az, hogy irodába bementem, és a Magdolnától "
       "olyan szinten ki vagyok borulva, hogy legszívesebben elzavarnám.")
out = split_sentence(ami)
check("'ami ..., az, hogy' correlative is not cut", "legnehezebb volt, az, hogy irodába" in out, out)
check("the cut happens at 'és' instead", ". És a Magdolnától" in out, out)
ami2 = "De ami az igazán legnehezebb volt, az hogy irodába bementem, és a Magdolnától olyan szinten ki vagyok borulva, hogy elzavarnám."
check("'az hogy' without its comma is not cut either", "volt, az hogy irodába" in split_sentence(ami2), split_sentence(ami2))

enum = "Tehát ahol van a beállítások, fájlátírás, előzmények, névjegy, kilépés, oda kéne egy gomb."
out = split_sentence(enum)
check("enumeration items are not turned into sentences",
      "beállítások, fájlátírás, előzmények, névjegy, kilépés" in out, out)

# --- whole messages ------------------------------------------------------------
msg = "Szia! " + seven + "\nMásodik bekezdés, egy, kettő, három, négy és öt, meg hat, meg hét."
out = split_long_sentences(msg)
check("paragraphs survive", out.count("\n") == 1, out)
check("greeting untouched", out.startswith("Szia! "), out)
check("words unchanged across the whole message", words_only(out) == words_only(msg))
check("decimal numbers untouched", split_sentence("Az ára 1,5 millió, ami sok, de oké, megveszem.").count("1,5") == 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
