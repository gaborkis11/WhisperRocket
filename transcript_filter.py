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
# The same word three or more times in a row is the decoder looping, not
# speech ("azoknak azoknak azoknak ..." eighteen times, 2026-09-03). Twice
# can be a real stutter or emphasis and is left to the cleanup.
_REPEAT = re.compile(r"\b(\w+)(?:[ ,]+\1\b){2,}", re.IGNORECASE | re.UNICODE)
# A phrase of three or more words said twice in a row verbatim is the same
# loop at phrase level ("... stílus profil promptok fogalmazómód meg minden
# ilyen dolgokat" three times over, 2026-09-03); a person does not repeat
# six words letter for letter.
_REPEAT_PHRASE = re.compile(r"\b((?:\w+[ ,]+){2,19}\w+)(?:[ ,]+\1\b)+", re.IGNORECASE | re.UNICODE)
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
    text = _REPEAT_PHRASE.sub(r"\1", text)
    text = _REPEAT.sub(r"\1", text)
    kept: List[str] = []
    for sentence in _SENTENCE.split(text.strip()):
        if sentence.strip() and not is_hallucination(sentence):
            kept.append(sentence.strip())
    return " ".join(kept)
