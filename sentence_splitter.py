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
touched. A comma is left alone when Hungarian grammar owns it: before a
subordinator ("hogy", "mert", "ha", "aki", "ami", ...), before the second
half of a correlative pair ("ha ..., akkor ..."), and inside enumerations
(short items on either side).
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

# The second half of "ha ..., akkor ..." / "amikor ..., akkor ..." pairs.
CORRELATIVE_OPENERS = ("ha ", "hogyha ", "amikor ", "amint ", "mihelyt ", "miután ")
CORRELATIVE_CLOSERS = frozenset(["akkor", "úgy", "annál", "az", "azt", "arra"])

_SENTENCE_END = re.compile(r"(?<=[.!?…])\s+")
_COMMA = re.compile(r",\s+")
_MIN_WORDS_EACH_SIDE = 3


def _first_word(segment: str) -> str:
    words = segment.split()
    return words[0].lower().strip("\"„”«»'‘’(") if words else ""


def _splittable(before: str, after: str) -> bool:
    nxt = _first_word(after)
    if not nxt or nxt in SUBORDINATORS:
        return False
    if nxt in CORRELATIVE_CLOSERS and any(o in f" {before.lower()}" for o in CORRELATIVE_OPENERS):
        return False
    # Enumerations and short tails ("backup, restart és update"; "..., oké")
    if len(before.split()) < _MIN_WORDS_EACH_SIDE or len(after.split()) < _MIN_WORDS_EACH_SIDE:
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
    for piece in pieces[1:]:
        current = out[-1]
        # Split whenever it is allowed: fewer commas per sentence is the
        # point, and a comma-free sentence is what the speaker writes himself
        if _splittable(current, piece):
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
