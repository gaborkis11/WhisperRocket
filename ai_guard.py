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

# Only phrases that can ONLY be a model talking about its own task. An earlier
# version also listed "i cannot", "i'm sorry" and "sajnalom, de" - which are
# ordinary ways to open a message. Found in testing: "help me write a message
# saying I cannot make it tomorrow" produced a perfectly good composed message
# starting "I cannot make it...", and the guard threw it away.
#
# Genuine refusals are caught by the length and retention checks instead: a
# response that declines the task shares almost no content with the transcript.
_META_PREFIXES: Sequence[str] = (
    "as an ai", "mint egy ai", "mint mesterseges intelligencia",
    "nem all modomban", "a tisztitott szoveg", "a megtisztitott",
    "ime a", "ime:", "itt van a tisztitott", "here is the cleaned",
    "here is the corrected", "here's the cleaned", "here's the corrected",
)

# Leading label lines the model sometimes prepends, e.g. "Tisztított szöveg:"
_LABEL_LINE = re.compile(r"^[^\n:]{0,40}:\s*\n+", re.IGNORECASE)

_QUOTE_PAIRS = (('"', '"'), ("'", "'"), ("„", "”"), ("“", "”"),
                ("«", "»"), ("‘", "’"))

# Per-mode tolerances. Transcript mode must not reword, so it is strict.
# Compose mode is supposed to reformulate, so its retention floor is only there
# to catch a response that has nothing to do with the transcript at all - a
# refusal shares almost no content words, a genuine rewrite shares plenty.
# max_novelty: share of the output's content words the speaker never said.
# Calibrated on 139 real cleanups (2026-09-03): the two answers the model gave
# instead of a transcript ("Igen, itt vagyok, hallak") scored 0.50 and 0.60,
# and at 0.40 exactly one good cleanup is caught with them (a misheard word
# fixed from context) - which a retry then usually resolves.
_THRESHOLDS = {
    "transcript": {"min_ratio": 0.5, "max_ratio": 1.6, "min_retention": 0.6,
                   "max_novelty": 0.40},
    "compose": {"min_ratio": 0.25, "max_ratio": 3.5, "min_retention": 0.15,
                "max_novelty": 1.0},
}

# Things that must come through a cleanup untouched: a web address, an e-mail
# address, a number of four or more digits (a phone number, a year, an
# amount). Short numbers are deliberately not on the list - "hat óra
# tizenötkor" legitimately turns into "6:15-kor".
_ENTITY = re.compile(
    r"(?:https?://\S+|www\.\S+|[\w.+-]+@[\w-]+\.[\w.]+|(?<!\d)\d{4,}(?!\d))",
    re.IGNORECASE,
)

_TRANSCRIPT_TAG = re.compile(r"</?transcript>", re.IGNORECASE)


@dataclass
class GuardResult:
    """
    Verdict on one model response.

    `soft` is True when every failure is one the caller may still accept after
    a retry did no better - today that is only a reordering, where the raw
    transcript (no punctuation, no capitals) would serve the user worse than
    two swapped words do.
    """
    ok: bool
    text: str
    failures: List[str] = field(default_factory=list)
    soft: bool = False

    @property
    def reason(self) -> str:
        return ", ".join(self.failures)


# Failures the caller may accept after one retry (see GuardResult.soft)
SOFT_FAILURES = ("reordered",)


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

    # The transcript reaches the model inside <TRANSCRIPT> tags; an echoed tag
    # is packaging, not content
    text = _TRANSCRIPT_TAG.sub("", text).strip()

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


# Verbal prefixes a swear word can carry: "kibaszott", "lebasz", "elkurv".
_VERBAL_PREFIXES: Sequence[str] = (
    "ki", "be", "le", "fel", "meg", "el", "at", "szet", "ossze", "ra", "oda",
    "vissza", "hozza", "agyon",
)


def _has_stem(words: List[str], stem: str) -> bool:
    """
    Whether a stem starts one of these words, on its own or after a verbal
    prefix. A plain substring test rejected a good cleanup because "sushit"
    contains "shit" (2026-09-03) - the one direction where a false positive
    throws away correct output must not match inside unrelated words.
    """
    for word in words:
        if word.startswith(stem):
            return True
        for prefix in _VERBAL_PREFIXES:
            if word.startswith(prefix) and word[len(prefix):].startswith(stem):
                return True
    return False


def _lcs_length(a: List[str], b: List[str]) -> int:
    """Length of the longest common subsequence (small inputs, O(n*m))"""
    previous = [0] * (len(b) + 1)
    for x in a:
        current = [0]
        for j, y in enumerate(b):
            current.append(previous[j] + 1 if x == y else max(previous[j + 1], current[j]))
        previous = current
    return previous[-1]


def reordered_words(raw_text: str, text: str, min_length: int = 5) -> int:
    """
    How many content words changed places between transcript and output.

    Over the content words both texts share (as a multiset), M is their count
    and L the longest common subsequence; M - L is the number that could only
    be matched out of order. Deleting filler, splitting a sentence and turning
    a number into digits never lower L relative to M, so any positive value
    is a real swap - "figyelj bazdmeg" coming back as "Bazdmeg, figyelj" gives
    1. Restricted to content words because short function words ("a" / "az")
    get substituted legitimately and made the plain-word version fire on 11%
    of good cleanups (measured 2026-09-03); on content words it fires on 2%.
    """
    def sequence(t: str) -> List[str]:
        return [w for w in _words(normalize(t))
                if len(w) >= min_length and w not in FILLER_WORDS]

    raw_seq, out_seq = sequence(raw_text), sequence(text)
    counts_raw: dict = {}
    for w in raw_seq:
        counts_raw[w] = counts_raw.get(w, 0) + 1
    counts_out: dict = {}
    for w in out_seq:
        counts_out[w] = counts_out.get(w, 0) + 1
    common = {w: min(c, counts_out.get(w, 0)) for w, c in counts_raw.items()
              if counts_out.get(w)}
    matched = sum(common.values())
    if matched < 2:
        return 0
    raw_common = [w for w in raw_seq if w in common]
    out_common = [w for w in out_seq if w in common]
    return matched - _lcs_length(raw_common, out_common)


def missing_entities(raw_text: str, text: str) -> List[str]:
    """Addresses and long numbers from the transcript that the output lost"""
    present = set(_ENTITY.findall(text))
    return [e for e in _ENTITY.findall(raw_text) if e not in present]


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
          extra_profanity: Sequence[str] = (),
          allowed_terms: Sequence[str] = ()) -> GuardResult:
    """
    Decide whether the model's response may replace the raw transcript.

    Args:
        raw_text: the transcript handed to the model
        model_text: what the model returned
        mode: "transcript" (strict) or "compose" (profanity only)
        extra_profanity: user-supplied stems, added to the built-in list
        allowed_terms: the user's dictionary - words the model may introduce
            (a name it resolved from how it sounded) without counting as new

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

    # Addition: core list only and matched at word start, because a false
    # positive here rejects good output
    raw_w, out_w = _words(raw_norm), _words(out_norm)
    added = {s for s in CORE_PROFANITY_STEMS
             if _has_stem(out_w, s) and not _has_stem(raw_w, s)}
    if added:
        failures.append("profanity_added(" + ",".join(sorted(added)) + ")")

    raw_content = content_words(raw_text)
    out_content = content_words(text)
    if limits["min_retention"] > 0 and raw_content:
        kept = raw_content & out_content
        retention = len(kept) / len(raw_content)
        if retention < limits["min_retention"]:
            failures.append(f"rewritten({retention:.2f})")

    # Novelty: the other direction. Retention says how much survived; this
    # says how much the model made up. A reply to the transcript ("Igen, itt
    # vagyok, hallak") keeps its one content word and adds everything else.
    if limits["max_novelty"] < 1.0 and out_content:
        allowed = set()
        for term in allowed_terms:
            allowed |= content_words(term)
        new = (out_content - raw_content) - allowed
        novelty = len(new) / len(out_content)
        if novelty > limits["max_novelty"]:
            failures.append(f"invented({novelty:.2f})")

    lost = missing_entities(raw_text, text)
    if lost:
        failures.append("entity_lost(" + ",".join(lost[:3]) + ")")

    if mode == "transcript":
        swapped = reordered_words(raw_text, text)
        if swapped:
            failures.append(f"reordered({swapped})")

    if failures:
        soft = all(f.startswith(SOFT_FAILURES) for f in failures)
        return GuardResult(False, raw_text, failures, soft)
    return GuardResult(True, text, [])
