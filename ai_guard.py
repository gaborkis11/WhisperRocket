#!/usr/bin/env python3
"""
WhisperRocket - AI output guard

The cleanup model is not trustworthy by default. Measured on this project with a
permissive prompt, Sonnet swapped the speaker and the addressee ("I will be
standing in the water" became "you will be"), invented a sentence that was never
said, and replaced "kurva elet" with the softer "Baszki". Dictation is often
used without watching the screen, so none of that gets noticed.

So every model response passes these checks before it is allowed near the
clipboard. A failed check is not an error: it means the raw transcript is used
instead, which is always faithful even when it is untidy.

The two checks that caught the real failure above:
  - profanity is preserved verbatim (the whole point of the project)
  - enough of the original content words survive (a rewrite is not a cleanup)

No network, no history, no memory. See ai_enhancer.py for the import rule.
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Sequence, Set

# Stems that must survive the cleanup untouched. Matched as substrings of the
# accent-stripped, lowercased text.
#
# Hungarian needs both "basz" and "bassz": "baszik" folds to a single s, while
# "basszus" has two, so one stem does not cover the other. Missing that meant
# the guard silently ignored "basszus" - found by measurement, not by reading.
#
# A false positive in THIS list is harmless: the check only fires for a stem
# already present in the input, and an unchanged word satisfies it. A false
# negative - a real swear word missing here - is what weakens the guard, so the
# list is generous, and includes insults too: softening "hulye" into "nem tul
# okos" is the same failure as softening a swear word.
PROFANITY_STEMS: Sequence[str] = (
    "kurv", "kuraf", "basz", "bassz", "bazd", "bazm", "fasz", "szar", "pics",
    "geci", "buzi", "kocsog", "rohad", "franc", "istenit", "anyad", "pina",
    "szop", "csesz", "csessz", "kefel", "hugy", "fing", "mocsk", "okadek",
    "bakker", "vazz", "csicska", "nyald", "dogolj", "atkozott", "hulye",
    "idiota", "barom", "marha", "genny", "nyomi", "tetves", "retkes", "dilis",
    "segg", "dug", "fuck", "shit", "bitch", "damn",
)

# Checked in the other direction: the model must not put words in the speaker's
# mouth that they never said. Here a false positive DOES cause harm - it would
# reject good output - so this list holds only the unambiguous ones. "marha"
# (also beef), "dug" (also to plug in) and "segg" belong in the list above but
# not in this one.
CORE_PROFANITY_STEMS: Sequence[str] = (
    "kurv", "basz", "bassz", "bazd", "bazm", "fasz", "pics", "geci", "buzi",
    "kocsog", "csicska", "genny", "fuck", "shit", "bitch",
)

# Words the cleanup is explicitly allowed to delete, so they are excluded from
# the content-retention check. Anything outside this set is content.
FILLER_WORDS: Set[str] = {
    "hat", "szoval", "ize", "izé", "oo", "ooo", "oooo", "aa", "aaa", "eee",
    "ugye", "akkor", "most", "tehat", "ilyen", "olyan", "amugy", "mondjuk",
    "gyakorlatilag", "alapvetoen", "igazabol", "ugyhogy", "szerintem",
    "nemtudom", "hogyhogy", "ott", "meg", "mar", "csak", "azert", "persze",
}

# Only matched at the very start of the response, and kept deliberately tight:
# "nem tudom, mit csinaljak" is legitimate dictated content, so a loose list
# would reject good output.
_META_PREFIXES: Sequence[str] = (
    "sajnalom, de", "sajnalom de", "nem all modomban", "nem tudok segiteni",
    "i'm sorry", "im sorry", "i am sorry", "i cannot", "i can't", "i can not",
    "as an ai", "mint egy ai", "mint mesterseges intelligencia",
    "itt van a", "ime a", "ime:", "a tisztitott szoveg", "a megtisztitott",
    "here is the", "here's the",
)

# Leading label lines the model sometimes prepends, e.g. "Tisztított szöveg:"
_LABEL_LINE = re.compile(r"^[^\n:]{0,40}:\s*\n+", re.IGNORECASE)

_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("„", "”"), ("“", "”"),
                ("«", "»"), ("‘", "’"))

# Per-mode tolerances. Transcript mode must not reword, so it is strict.
# Compose mode is supposed to reformulate, so only profanity is policed.
_THRESHOLDS = {
    "transcript": {"min_ratio": 0.5, "max_ratio": 1.6, "min_retention": 0.6},
    "compose": {"min_ratio": 0.25, "max_ratio": 3.5, "min_retention": 0.0},
}


@dataclass
class GuardResult:
    """Verdict on one model response"""
    ok: bool
    text: str
    failures: List[str] = field(default_factory=list)

    @property
    def reason(self) -> str:
        return ", ".join(self.failures)


def normalize(text: str) -> str:
    """Lowercase and strip accents, so 'Kurvára' and 'kurvara' compare equal"""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def _words(normalized: str) -> List[str]:
    return re.findall(r"[0-9a-z]+", normalized)


def strip_wrapper(text: str) -> str:
    """
    Remove the packaging the model sometimes adds around the message itself:
    code fences, a leading label line, and surrounding quotes.
    """
    text = text.strip()

    # Code fence, with or without a language tag
    fenced = re.match(r"^```[a-z]*\s*\n(.*?)\n?```$", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    text = _LABEL_LINE.sub("", text, count=1).strip()

    # Quotes wrapping the whole response (only when there is no inner quote of
    # the same kind, so a legitimately quoted phrase inside is left alone)
    for open_q, close_q in _QUOTE_PAIRS:
        if len(text) >= 2 and text.startswith(open_q) and text.endswith(close_q):
            inner = text[len(open_q):-len(close_q)]
            if open_q not in inner and close_q not in inner:
                text = inner.strip()
                break

    return text


def found_profanity(text: str) -> Set[str]:
    """Which profanity stems appear in this text"""
    normalized = normalize(text)
    return {stem for stem in PROFANITY_STEMS if stem in normalized}


def content_words(text: str, min_length: int = 5) -> Set[str]:
    """
    Content words as 5-character stems, so Hungarian suffixes don't cause false
    misses ('szerelo' / 'szerelot' both become 'szere').

    Kept at 5 characters deliberately: it is short enough to absorb inflection
    but long enough that a person swap - 'fogok' vs 'fogsz' - still registers as
    a different word, which is exactly the failure this check exists to catch.
    """
    stems = set()
    for word in _words(normalize(text)):
        if len(word) < min_length or word in FILLER_WORDS:
            continue
        stems.add(word[:min_length])
    return stems


def check(raw_text: str, model_text: str, mode: str = "transcript",
          extra_profanity: Sequence[str] = ()) -> GuardResult:
    """
    Decide whether the model's response may replace the raw transcript.

    Args:
        raw_text: the transcript handed to the model
        model_text: what the model returned
        mode: "transcript" (strict) or "compose" (profanity only)
        extra_profanity: user-supplied stems, added to the built-in list

    Returns:
        GuardResult. When ok is False, the caller must use raw_text.
    """
    limits = _THRESHOLDS.get(mode, _THRESHOLDS["transcript"])
    failures: List[str] = []

    text = strip_wrapper(model_text or "")

    if not text:
        return GuardResult(False, raw_text, ["empty"])

    normalized_start = normalize(text)[:60]
    if any(normalized_start.startswith(p) for p in _META_PREFIXES):
        failures.append("meta_or_refusal")

    raw_words = _words(normalize(raw_text))
    out_words = _words(normalize(text))
    if raw_words:
        ratio = len(out_words) / len(raw_words)
        if ratio < limits["min_ratio"]:
            failures.append(f"too_short({ratio:.2f})")
        elif ratio > limits["max_ratio"]:
            failures.append(f"too_long({ratio:.2f})")

    raw_norm, out_norm = normalize(raw_text), normalize(text)

    # Preservation: generous list, because a false positive here costs nothing
    keep_stems = tuple(PROFANITY_STEMS) + tuple(
        normalize(s) for s in extra_profanity if s
    )
    softened = {s for s in keep_stems if s in raw_norm and s not in out_norm}
    if softened:
        failures.append("profanity_softened(" + ",".join(sorted(softened)) + ")")

    # Addition: core list only, because a false positive here rejects good output
    added = {s for s in CORE_PROFANITY_STEMS if s in out_norm and s not in raw_norm}
    if added:
        failures.append("profanity_added(" + ",".join(sorted(added)) + ")")

    if limits["min_retention"] > 0:
        raw_content = content_words(raw_text)
        if raw_content:
            kept = raw_content & content_words(text)
            retention = len(kept) / len(raw_content)
            if retention < limits["min_retention"]:
                failures.append(f"rewritten({retention:.2f})")

    if failures:
        return GuardResult(False, raw_text, failures)
    return GuardResult(True, text, [])
