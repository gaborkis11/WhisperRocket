#!/usr/bin/env python3
"""
Guards updates.json - the bilingual changelog the in-app update dialog
renders. Fails the build when an entry is malformed, a language is missing,
or the app's own APP_VERSION has no entry (so a release can never ship
without its notes).

    python3 tests/test_updates_json.py
"""
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

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


def version_tuple(text):
    parts = []
    for part in str(text).lstrip("v").split("."):
        parts.append(int(part) if part.isdigit() else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def main():
    data = json.loads((REPO_ROOT / "updates.json").read_text())
    versions = data.get("versions", [])
    check("versions list is non-empty", len(versions) > 0)

    ok_fields = all(
        isinstance(v.get("version"), str) and isinstance(v.get("date"), str)
        and isinstance(v.get("notes"), dict) for v in versions)
    check("every entry has version/date/notes", ok_fields)

    ok_langs = all(
        isinstance(v["notes"].get("en"), list) and v["notes"]["en"]
        and all(isinstance(line, str) and line for line in v["notes"]["en"])
        and isinstance(v["notes"].get("hu"), list) and v["notes"]["hu"]
        and all(isinstance(line, str) and line for line in v["notes"]["hu"])
        for v in versions)
    check("every entry has non-empty EN and HU notes", ok_langs)

    tuples = [version_tuple(v["version"]) for v in versions]
    check("versions strictly descending (newest first)",
          all(a > b for a, b in zip(tuples, tuples[1:])), f"got {tuples}")

    # APP_VERSION from source text - about_window imports PySide6, which CI
    # does not have, so read the constant instead of importing the module.
    source = (REPO_ROOT / "about_window.py").read_text()
    match = re.search(r'APP_VERSION\s*=\s*"([^"]+)"', source)
    check("APP_VERSION found in about_window.py", match is not None)
    if match:
        app_version = version_tuple(match.group(1))
        check(f"APP_VERSION {match.group(1)} has an updates.json entry",
              app_version in tuples, f"entries: {tuples}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
