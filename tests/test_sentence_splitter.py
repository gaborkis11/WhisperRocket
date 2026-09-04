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

frag = ("És most már itthon vagyok, ezért tudok veled beszélni, nem a Jarvison keresztül, "
        "és van itt ez a személyes fájlod, a személyes fájlok, ugye, az annyi van, hogy oda van beállítva.")
out = split_sentence(frag)
check("no cut before a word a sentence cannot open with ('nem', 'a', 'ugye')",
      ". Nem" not in out and ". A személyes" not in out and ". Ugye" not in out, out)
check("cuts still happen before 'ezért' and 'és'", ". Ezért" in out and ". És van" in out, out)
short = "Ezt megnéztem, meg minden ilyen dolgot, mondjuk itt nálam, tehát ennyi volt ma, és kész."
out = split_sentence(short)
check("a tail shorter than four words is never made a sentence", ". És kész" not in out, out)
check("'meg' and 'mondjuk' never open a sentence", ". Meg" not in out and ". Mondjuk" not in out, out)

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

kozben = "Azért, e közben, miközben a tesztelést is nézed, akkor válaszolj a kérdésemre is, mert ezek reális kérdések."
out = split_sentence(kozben)
check("'miközben' is a subordinator, no cut in front of it", ". Miközben" not in out, out)
check("'miközben ..., akkor' is a pair, no cut in front of 'akkor'", ". Akkor" not in out, out)

amennyiben = "Amennyiben ez így van, akkor a stílusprofilt ugyanígy írjuk oda, hogy amennyiben be van kapcsolva az AI, akkor használódik ez a profil."
check("'amennyiben ..., akkor' is a pair", ". Akkor" not in split_sentence(amennyiben), split_sentence(amennyiben))

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
