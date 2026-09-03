#!/usr/bin/env python3
"""
WhisperRocket - filter for what the recogniser writes on silence.

Whisper was trained on subtitled video, so on a stretch of silence - the end
of a recording, a pause - it writes what subtitles say there: "Feliratot
készítette Amara.org közössége", "Feliratok az Amara.org közösségétől", "Ha
tetszett, kapcsold be az angol feliratot". Measured in this user's history:
these three phrases account for every hallucination found in 3400
dictations; the word "felirat" on its own is a legitimate word (a caption in
a UI) and must not be touched.

Runs on the raw transcript before anything else sees it, so the phrase is
gone even when the AI cleanup does not run. Bracketed stage directions -
"[zene]", "(nevetés)" - are dropped the same way: nobody dictates brackets.
"""
import re
import unicodedata
from typing import List

# Matched on lowercase, accent-stripped text; each entry is a phrase the
# recogniser produces on silence, never something a person dictates.
HALLUCINATION_PHRASES = (
    "feliratot keszitette",
    "feliratok az amara",
    "amara.org",
    "ha tetszett, kapcsold be az angol feliratot",
    "kapcsold be az angol feliratot",
    "koszonom a figyelmet",
    "koszonjuk a figyelmet",
    "a videot keszitette",
    "feliratozta:",
    "iratkozz fel a csatornara",
    "subtitles by the amara",
    "thank you for watching",
    "thanks for watching",
)

_BRACKETED = re.compile(r"\s*[\[\(\{][^\]\)\}]{0,80}[\]\)\}]")
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def is_hallucination(sentence: str) -> bool:
    """Whether one sentence is a subtitle-credit style hallucination"""
    normalized = _normalize(sentence)
    return any(phrase in normalized for phrase in HALLUCINATION_PHRASES)


def filter_transcript(text: str) -> str:
    """
    The transcript without stage directions and silence hallucinations.

    Whole sentences go: the hallucination is never part of what was said, so
    there is nothing in that sentence to keep. Returns "" when nothing real is
    left, which callers treat as "no speech".
    """
    if not text:
        return text
    text = _BRACKETED.sub("", text)
    kept: List[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        if sentence.strip() and not is_hallucination(sentence):
            kept.append(sentence.strip())
    return " ".join(kept)
