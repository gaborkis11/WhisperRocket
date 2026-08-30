#!/usr/bin/env python3
"""
Guards that every translation key used in code exists in the EN dict, so a
checkbox can never render as a raw key like "update_check_setting" (seen
once on a machine running mixed file versions - this locks the class out
of the repo itself). HU parity is enforced separately by
tests/test_translations.py.

    python3 tests/test_translation_keys_used.py
"""
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from translations import TRANSLATIONS

KEY_PATTERN = re.compile(r"""\bt\(\s*["']([a-z0-9_]+)["']""")


def main():
    en_keys = set(TRANSLATIONS["en"])
    used = {}
    for path in REPO_ROOT.glob("*.py"):
        if path.name.startswith("test"):
            continue
        for match in KEY_PATTERN.finditer(path.read_text()):
            used.setdefault(match.group(1), path.name)
    for path in (REPO_ROOT / "platform_support").glob("*.py"):
        for match in KEY_PATTERN.finditer(path.read_text()):
            used.setdefault(match.group(1), f"platform_support/{path.name}")

    missing = sorted(k for k in used if k not in en_keys)
    print(f"used keys: {len(used)}")
    if missing:
        for key in missing:
            print(f"FAIL  t(\"{key}\") in {used[key]} has no EN translation")
        return 1
    print("PASS  every t() key used in code exists in the EN dict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
