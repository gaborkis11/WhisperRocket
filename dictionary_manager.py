#!/usr/bin/env python3
"""
WhisperRocket - Custom dictionary

Speech recognition reliably mangles the proper nouns a particular person uses -
names, product names, places. A model can guess some of them back from context,
but guessing is exactly what we do not want in transcript mode.

So the fix happens in code, before the model ever sees the text: a plain lookup
table replaces known mishearings. It costs no tokens, cannot hallucinate, and
works even with the AI enhancement switched off entirely.

Entries marked "low" confidence are not replaced automatically - they are passed
to the model as a hint instead, so it can decide from context. That is the
"both" strategy: deterministic where we are sure, model-assisted where we aren't.

File: ~/.config/whisperrocket/dictionary.json  (never committed)

    {
      "version": 1,
      "entries": [
        {"correct": "Tailscale", "heard": ["tail scale"], "confidence": "high"},
        {"correct": "Kubernetes", "heard": ["kubernetesz"], "confidence": "low"}
      ]
    }
"""
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from platform_support import get_platform_handler

DICTIONARY_FILENAME = "dictionary.json"
CURRENT_VERSION = 1

CONFIDENCE_HIGH = "high"
CONFIDENCE_LOW = "low"


def get_dictionary_path() -> Path:
    """Path to the user's dictionary (never inside the project directory)"""
    config_dir = get_platform_handler().get_config_dir()
    return config_dir / DICTIONARY_FILENAME


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


def load() -> Dict:
    """
    Read the dictionary. A missing or broken file yields an empty one - this
    runs inside the dictation path and must never raise.
    """
    path = get_dictionary_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"version": CURRENT_VERSION, "entries": []}

    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return {"version": CURRENT_VERSION, "entries": []}
    return data


def save(data: Dict) -> bool:
    """Write the dictionary back, creating the config directory if needed"""
    path = get_dictionary_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def _valid_entries(data: Optional[Dict] = None) -> List[Dict]:
    """Entries that have both a replacement and something to match against"""
    data = data if data is not None else load()
    entries = []
    for entry in data.get("entries", []):
        if not isinstance(entry, dict):
            continue
        correct = str(entry.get("correct") or "").strip()
        heard = entry.get("heard") or []
        if not correct or not isinstance(heard, list):
            continue
        variants = [str(h).strip() for h in heard if str(h).strip()]
        if not variants:
            continue
        entries.append({
            "correct": correct,
            "heard": variants,
            "confidence": str(entry.get("confidence") or CONFIDENCE_HIGH).lower(),
        })
    return entries


def _variant_pattern(variant: str, allow_suffix: bool = False) -> re.Pattern:
    """
    Word-bounded pattern for one misheard variant, tolerant of extra spaces.

    allow_suffix widens the match over a short Hungarian case ending, so
    "kubernetesz" also matches "kuberneteszt". That is right for a hint the model
    weighs against context, and wrong for an automatic replacement - turning
    "reszelo" into "Reszelot" because "reszel" was listed is exactly the false
    positive this feature must not produce - so apply() leaves it off.
    """
    parts = [re.escape(fold(part)) for part in variant.split() if part]
    if not parts:
        return re.compile(r"(?!)")
    body = r"\s+".join(parts)
    tail = r"\w{0,4}" if allow_suffix else ""
    return re.compile(r"\b" + body + tail + r"\b")


def apply(text: str, data: Optional[Dict] = None) -> Tuple[str, int]:
    """
    Replace known mishearings with the correct spelling.

    Only "high" confidence entries are replaced; "low" ones go to prompt_hint().
    Matching ignores case and accents, but the replacement keeps the spelling
    from the dictionary, so "tail scale" becomes "Tailscale" and not "tailscale".

    Returns:
        (corrected_text, number_of_replacements)
    """
    if not text or not text.strip():
        return text, 0

    entries = [e for e in _valid_entries(data) if e["confidence"] != CONFIDENCE_LOW]
    if not entries:
        return text, 0

    # Longest variants first, so "tail scale drive" wins over "tail scale"
    replacements: List[Tuple[re.Pattern, str]] = []
    for entry in entries:
        for variant in sorted(entry["heard"], key=len, reverse=True):
            replacements.append((_variant_pattern(variant), entry["correct"]))

    result = text
    count = 0
    for pattern, correct in replacements:
        folded = fold(result)
        spans = [m.span() for m in pattern.finditer(folded)]
        if not spans:
            continue
        # Right to left, so earlier spans keep their indices valid
        for start, end in reversed(spans):
            if result[start:end] == correct:
                continue
            result = result[:start] + correct + result[end:]
            count += 1

    return result, count


def prompt_hint(text: str, data: Optional[Dict] = None, max_entries: int = 25) -> str:
    """
    Hint lines for the low-confidence entries that are actually relevant to this
    transcript, so the model can decide from context.

    Only relevant entries are included - sending the whole dictionary would cost
    tokens on every dictation and bury the useful ones.
    """
    if not text or not text.strip():
        return ""

    folded_text = fold(text)
    lines = []
    for entry in _valid_entries(data):
        if entry["confidence"] != CONFIDENCE_LOW:
            continue
        for variant in entry["heard"]:
            if _variant_pattern(variant, allow_suffix=True).search(folded_text):
                lines.append(f'- "{variant}" -> {entry["correct"]}')
                break
        if len(lines) >= max_entries:
            break

    return "\n".join(lines)


def stats(data: Optional[Dict] = None) -> Dict[str, int]:
    """Entry counts for the Settings UI"""
    entries = _valid_entries(data)
    return {
        "total": len(entries),
        "high": sum(1 for e in entries if e["confidence"] != CONFIDENCE_LOW),
        "low": sum(1 for e in entries if e["confidence"] == CONFIDENCE_LOW),
    }


def import_from_file(source_path: str) -> Tuple[bool, str]:
    """
    Validate a dictionary file the user picked and copy it into the config dir.

    Returns:
        (success, message) - the message names the problem when it fails
    """
    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"invalid JSON: {e}"
    except Exception as e:
        return False, str(e)

    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        return False, "expected an object with an 'entries' list"

    valid = _valid_entries(data)
    if not valid:
        return False, "no usable entries (each needs 'correct' and 'heard')"

    data.setdefault("version", CURRENT_VERSION)
    if not save(data):
        return False, "could not write to the config directory"
    return True, f"{len(valid)} entries imported"


if __name__ == "__main__":
    import sys

    sample = sys.argv[1] if len(sys.argv) > 1 else "megy a tail scale meg a kubernetesz"
    fixed, n = apply(sample)
    print(f"path:     {get_dictionary_path()}")
    print(f"stats:    {stats()}")
    print(f"input:    {sample}")
    print(f"output:   {fixed}   ({n} replacements)")
    hint = prompt_hint(sample)
    print(f"hint:     {hint or '-'}")
