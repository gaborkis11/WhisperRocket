#!/usr/bin/env python3
"""
Every UI string must exist in both languages.

A key present in one language and missing in the other does not fail loudly in
the app - the fallback quietly shows the wrong language - so parity is checked
here instead.

    python3 tests/test_translations.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from translations import TRANSLATIONS

failed = False
en, hu = set(TRANSLATIONS["en"]), set(TRANSLATIONS["hu"])

for label, missing in (("hu", en - hu), ("en", hu - en)):
    if missing:
        failed = True
        print(f"FAIL  keys missing from '{label}': {sorted(missing)}")

for lang in ("en", "hu"):
    empty = [key for key, value in TRANSLATIONS[lang].items() if not str(value).strip()]
    if empty:
        failed = True
        print(f"FAIL  empty values in '{lang}': {empty}")

if failed:
    sys.exit(1)
print(f"PASS  {len(en)} keys, present and non-empty in both languages")
