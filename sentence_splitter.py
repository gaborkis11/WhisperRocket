#!/usr/bin/env python3
"""
WhisperRocket - sentence splitter for comma-heavy cleanup output.

The speaker dislikes comma-heavy sentences: at most two commas in a sentence,
and a full stop where the third would come. The cleanup model does not do
this on its own at the effort we can afford - measured on eight real
dictations, three prompt wordings, a user-turn reminder and medium effort all
left 14-15 commas per 100 words (2026-09-03). Punctuation is deterministic,
so this does it in code, after the guard has accepted the model's text.

Only commas become full stops and the next word gets a capital; no word is
touched. A comma is left alone when grammar owns it - before a subordinator
("hogy", "mert", "ha", "aki", "ami", ...), between the halves of a
correlative pair ("ha ..., akkor ...") - when the next word cannot open a
sentence ("nem", "a", "meg", "ugye", ...), and inside an enumeration.
"""
import re
from typing import List

# The comma before these belongs to grammar, not to rhythm.
SUBORDINATORS = frozenset("""
hogy mert ha aki akik akit akinek ami amik amit aminek amely amelyek amelyet
ahol ahova ahonnan amikor amíg amint ahogy ahogyan mint mivel hiszen mielőtt
miután mióta hogyha noha bár habár jóllehet amennyire amennyiben miért mi ki
kik hol mikor hova honnan mennyi mennyire milyen melyik merre meddig
""".split())

# The second half of a correlative pair: "ha ..., akkor ...", "ami ..., az
# ...", "aki ..., annak ...". Cutting between the halves leaves a fragment
# ("De ami a legnehezebb volt. Az hogy bementem." - seen 2026-09-03).
CORRELATIVE_OPENERS = ("ha ", "hogyha ", "amikor ", "amint ", "mihelyt ", "miután ",
                       "ami ", "amit ", "aki ", "akit ", "amelyik ", "amely ",
                       "amennyi ", "ahol ", "ahogy ", "amiért ")
CORRELATIVE_CLOSERS = frozenset(["akkor", "úgy", "annál", "az", "azt", "arra", "annak",
                                 "abban", "abból", "annyi", "annyit", "ott", "úgy",
                                 "azért", "attól", "ahhoz", "amiatt"])

# Words a sentence does not open with: an article, a negation, a particle.
# Cutting in front of them produced fragments - "Nem a Jarvison keresztül.",
# "Meg minden ilyen dolgot.", "Mondjuk itt nálam." (2026-09-03). A whitelist
# of conjunctions instead was measured at 12.7 commas per 100 words against
# 10.9 for this rule, so the blacklist stays.
NEVER_OPENS = frozenset("""
a az egy nem ne sem se is csak meg még már ugye mondjuk persze talán szinte
épp éppen pont olyan ilyen annyira elég nagyon például vagy hát na
""".split())

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_COMMA = re.compile(r",\s+")
_MIN_WORDS_BEFORE = 3
_MIN_WORDS_AFTER = 3        # a shorter clause is an enumeration item
_MIN_WORDS_REMAINING = 4    # a shorter rest is a tail, not a sentence


def _first_word(segment: str) -> str:
    words = segment.split()
    return words[0].lower().strip("\"„”«»'‘’(") if words else ""


def _splittable(before: str, after: str, remaining: str) -> bool:
    """
    Whether the comma between `before` and `after` may become a full stop.
    `after` is the next clause, `remaining` the whole rest of the sentence.
    """
    nxt = _first_word(after)
    if not nxt or nxt in SUBORDINATORS or nxt in NEVER_OPENS:
        return False
    if nxt in CORRELATIVE_CLOSERS and any(o in f" {before.lower()}" for o in CORRELATIVE_OPENERS):
        return False
    # "..., az hogy ..." / "..., az, hogy ...": the pronoun only introduces the
    # clause, a sentence cannot start with it
    after_words = after.split()
    if nxt in ("az", "azt", "annak", "arra", "abban") and len(after_words) > 1 \
            and after_words[1].lower().strip(",") == "hogy":
        return False
    # Enumerations and short tails ("backup, restart és update"; "..., és kész")
    if len(before.split()) < _MIN_WORDS_BEFORE or len(after.split()) < _MIN_WORDS_AFTER \
            or len(remaining.split()) < _MIN_WORDS_REMAINING:
        return False
    return True


def _capitalise(segment: str) -> str:
    for i, ch in enumerate(segment):
        if ch.isalpha():
            return segment[:i] + ch.upper() + segment[i + 1:]
    return segment


def split_sentence(sentence: str, max_commas: int = 2) -> str:
    """One sentence; commas beyond max_commas become sentence ends where allowed."""
    if sentence.count(",") <= max_commas:
        return sentence
    pieces = _COMMA.split(sentence)
    if len(pieces) < 2:
        return sentence
    out: List[str] = [pieces[0]]
    for index, piece in enumerate(pieces[1:], start=1):
        current = out[-1]
        remaining = ", ".join(pieces[index:])
        # Split whenever it is allowed: fewer commas per sentence is the
        # point, and a comma-free sentence is what the speaker writes himself
        if _splittable(current, piece, remaining):
            out[-1] = current.rstrip() + "."
            out.append(_capitalise(piece))
        else:
            out[-1] = current + ", " + piece
    return " ".join(out)


def split_long_sentences(text: str, max_commas: int = 2) -> str:
    """The whole message, paragraph structure kept."""
    paragraphs = text.split("\n")
    result = []
    for paragraph in paragraphs:
        sentences = _SENTENCE_END.split(paragraph)
        result.append(" ".join(split_sentence(s, max_commas) for s in sentences))
    return "\n".join(result)
