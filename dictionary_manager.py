#!/usr/bin/env python3
"""
WhisperRocket - Personal vocabulary

Speech recognition does not know the words a particular person uses - project
names, product names, people, in-house jargon - and it does not fail quietly.
Measured on this project: "tel szkel" came back as TeamViewer, a real product
that was never mentioned. A wrong-but-plausible name in a message is worse than
a garbled one, because nobody notices it.

The fix is to tell the model which words exist. Measured, three runs out of
three: given nothing but a list of correct spellings - no hint about what the
recogniser produces instead - Sonnet resolved every mangled term, Hungarian
inflection included ("klovolt ba" -> "ClawVaultba"). So the file is just a list
of words, which is the least work possible for the person writing it.

A term may optionally spell out what it gets misheard as. Those get replaced in
code, before the model runs, which is the only way to fix them when the AI
cleanup is switched off entirely.

File: ~/.config/whisperrocket/dictionary.md  (never committed)

    # Comments are ignored. One word per line, spelled the way you want it.
    Tailscale
    WhisperRocket

    # With a colon, the mishearing is corrected in code as well:
    Tailscale: tail scale, telszkel
"""
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from platform_support import get_platform_handler

DICTIONARY_FILENAME = "dictionary.md"
LEGACY_JSON_FILENAME = "dictionary.json"

# The whole vocabulary goes into every prompt, so it needs a ceiling. 300 terms
# is roughly 600 tokens - a fraction of a cent per dictation - and far more than
# anyone maintains by hand.
MAX_VOCABULARY = 300

def get_dictionary_path() -> Path:
    """Path to the user's vocabulary (never inside the project directory)"""
    return get_platform_handler().get_config_dir() / DICTIONARY_FILENAME


def get_legacy_json_path() -> Path:
    return get_platform_handler().get_config_dir() / LEGACY_JSON_FILENAME


def _fold_char(char: str) -> str:
    """
    Lowercase and strip the accent from a single character, always returning
    exactly one character.

    The 1:1 guarantee matters: matches are found in the folded text and spliced
    back into the original by index, so any length change would corrupt the
    output. Hungarian accented vowels all fold cleanly this way.
    """
    lowered = char.lower()
    if len(lowered) != 1:
        lowered = lowered[0]
    decomposed = unicodedata.normalize("NFD", lowered)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped[0] if stripped else lowered


def fold(text: str) -> str:
    """Accent-free lowercase copy of text, character-for-character"""
    return "".join(_fold_char(c) for c in text)


def parse(text: str) -> List[Dict]:
    """
    Parse the markdown file into terms.

    Returns a list of {"correct": str, "heard": [str, ...]}; an empty heard list
    means the term is vocabulary only, with no literal replacement.
    """
    terms: List[Dict] = []
    seen = set()

    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        line = line.lstrip("-*").strip()
        if not line:
            continue

        correct, _, variants_raw = line.partition(":")
        correct = correct.strip()
        if not correct:
            continue

        key = fold(correct)
        if key in seen:
            continue
        seen.add(key)

        variants = [v.strip() for v in variants_raw.split(",") if v.strip()]
        terms.append({"correct": correct, "heard": variants})

    return terms


def render(terms: List[Dict]) -> str:
    """Turn terms back into file text, keeping the colon form where needed"""
    lines = []
    for term in terms:
        correct = str(term.get("correct") or "").strip()
        if not correct:
            continue
        variants = [str(v).strip() for v in (term.get("heard") or []) if str(v).strip()]
        lines.append(f"{correct}: {', '.join(variants)}" if variants else correct)
    return "\n".join(lines) + ("\n" if lines else "")


def _migrate_legacy_json() -> Optional[str]:
    """
    Convert a dictionary.json written by an earlier version into the markdown
    file, once. The JSON format was harder to write by hand than it needed to
    be, and nobody should have to redo their list because the format improved.
    """
    legacy = get_legacy_json_path()
    try:
        data = json.loads(legacy.read_text(encoding="utf-8"))
    except Exception:
        return None

    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return None

    terms = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        correct = str(entry.get("correct") or "").strip()
        if not correct:
            continue
        heard = entry.get("heard") or []
        variants = [str(h).strip() for h in heard if str(h).strip()] \
            if isinstance(heard, list) else []
        # "low" confidence meant "do not replace, only hint" - which is now
        # simply a term with no variants.
        if str(entry.get("confidence") or "high").lower() == "low":
            variants = []
        terms.append({"correct": correct, "heard": variants})

    if not terms:
        return None

    text = render(terms)
    if write_text(text):
        try:
            legacy.rename(legacy.with_suffix(".json.migrated"))
        except Exception:
            pass
        print(f"[INFO] Vocabulary migrated from {legacy.name} to {DICTIONARY_FILENAME}")
    return text


def read_text() -> str:
    """
    Raw file contents for the editor, or "" when there is no file yet.

    Deliberately returns nothing rather than a template. The template belongs to
    the UI, which knows the user's language - and an earlier version seeded live
    example words here, so saving an untouched template silently made the
    examples someone's vocabulary.
    """
    path = get_dictionary_path()
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        pass

    migrated = _migrate_legacy_json()
    return migrated if migrated is not None else ""


def write_text(text: str) -> bool:
    """Write the file, creating the config directory if needed"""
    path = get_dictionary_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        return True
    except Exception:
        return False


def load() -> List[Dict]:
    """
    The parsed vocabulary. Never raises - this runs inside the dictation path.

    The template counts as empty: its example lines are commented out, so a user
    who opened the editor and closed it again has no vocabulary, not two words
    they never chose.
    """
    path = get_dictionary_path()
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = _migrate_legacy_json()
        if text is None:
            return []
    try:
        return parse(text)
    except Exception:
        return []


def vocabulary(terms: Optional[List[Dict]] = None) -> List[str]:
    """Correct spellings, for the prompt"""
    terms = load() if terms is None else terms
    return [t["correct"] for t in terms if t.get("correct")][:MAX_VOCABULARY]


def _variant_pattern(variant: str) -> re.Pattern:
    """Word-bounded pattern for one misheard variant, tolerant of extra spaces"""
    parts = [re.escape(fold(part)) for part in variant.split() if part]
    if not parts:
        return re.compile(r"(?!)")
    return re.compile(r"\b" + r"\s+".join(parts) + r"\b")


def apply(text: str, terms: Optional[List[Dict]] = None) -> Tuple[str, int]:
    """
    Replace spelled-out mishearings with the correct spelling.

    Only terms that name their variants are touched; the rest are the model's
    job. Matching ignores case and accents but respects word boundaries, so
    "tail scale" becomes "Tailscale" while "tailscalexyz" is left alone.

    Returns:
        (corrected_text, number_of_replacements)
    """
    if not text or not text.strip():
        return text, 0

    terms = load() if terms is None else terms
    replacements: List[Tuple[re.Pattern, str]] = []
    for term in terms:
        correct = term.get("correct")
        if not correct:
            continue
        # Longest variants first, so "tail scale drive" wins over "tail scale"
        for variant in sorted(term.get("heard") or [], key=len, reverse=True):
            replacements.append((_variant_pattern(variant), correct))

    if not replacements:
        return text, 0

    result = text
    count = 0
    for pattern, correct in replacements:
        folded = fold(result)
        spans = [m.span() for m in pattern.finditer(folded)]
        # Right to left, so earlier spans keep their indices valid
        for start, end in reversed(spans):
            if result[start:end] == correct:
                continue
            result = result[:start] + correct + result[end:]
            count += 1

    return result, count


def stats(terms: Optional[List[Dict]] = None) -> Dict[str, int]:
    """Counts for the Settings window"""
    terms = load() if terms is None else terms
    return {
        "total": len(terms),
        "with_variants": sum(1 for t in terms if t.get("heard")),
    }


def import_from_file(source_path: str) -> Tuple[bool, str]:
    """
    Copy a vocabulary file the user picked into the config directory.

    Accepts the markdown format and the JSON format an earlier version used, so
    a list generated by something else still loads.
    """
    try:
        raw = Path(source_path).read_text(encoding="utf-8")
    except Exception as e:
        return False, str(e)

    text = raw
    if source_path.lower().endswith(".json"):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return False, f"invalid JSON: {e}"
        entries = data.get("entries") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            return False, "expected an object with an 'entries' list"
        terms = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            correct = str(entry.get("correct") or "").strip()
            if not correct:
                continue
            heard = entry.get("heard") or []
            variants = [str(h).strip() for h in heard if str(h).strip()] \
                if isinstance(heard, list) else []
            if str(entry.get("confidence") or "high").lower() == "low":
                variants = []
            terms.append({"correct": correct, "heard": variants})
        text = render(terms)

    if not parse(text):
        return False, "no usable words found"

    if not write_text(text):
        return False, "could not write to the config directory"
    return True, f"{len(parse(text))} words imported"


if __name__ == "__main__":
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "megy a tail scale meg a viszper roket"
    terms = load()
    fixed, n = apply(sample, terms)
    print(f"path:       {get_dictionary_path()}")
    print(f"stats:      {stats(terms)}")
    print(f"vocabulary: {', '.join(vocabulary(terms)) or '-'}")
    print(f"input:      {sample}")
    print(f"output:     {fixed}   ({n} literal replacements)")
