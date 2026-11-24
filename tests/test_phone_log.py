#!/usr/bin/env python3
"""
Tests for phone_log.py - the lasting record of failed phone dictations.

Standard library only, writes into a temporary directory:

    python3 tests/test_phone_log.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import phone_log  # noqa: E402

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


with tempfile.TemporaryDirectory() as tmp:
    folder = Path(tmp) / "whisperrocket"
    phone_log.record(folder, 503, "not_ready", "100.64.0.7")
    phone_log.record(folder, 500, "failed", detail="RuntimeError: boom\nsecond line")
    log_file = folder / phone_log.LOG_FILENAME
    lines = log_file.read_text(encoding="utf-8").splitlines() if log_file.exists() else []

    check("the folder is created and one line is written per failure", len(lines) == 2, repr(lines))
    check("status, key and client are on the line",
          bool(lines) and lines[0].endswith("503 not_ready  100.64.0.7"), repr(lines[:1]))
    check("each line starts with a date and time",
          bool(lines) and lines[0][:4].isdigit() and lines[0][10] == " ", repr(lines[:1]))
    check("a multi-line exception stays on one line",
          len(lines) == 2 and lines[1].endswith("500 failed  RuntimeError: boom second line"), repr(lines))

    for _ in range(phone_log.LOG_MAX_BYTES // 40 + 50):
        phone_log.record(folder, 429, "busy", "100.64.0.7")
    sizes = [p.stat().st_size for p in folder.iterdir()]
    check("the log rotates instead of growing without bound",
          len(sizes) == 1 + phone_log.LOG_BACKUPS and max(sizes) <= phone_log.LOG_MAX_BYTES,
          repr(sizes))

blocker = Path(tempfile.mkdtemp()) / "not_a_dir"
blocker.write_text("x")
try:
    phone_log.record(blocker, 401, "bad_token")
    check("an unwritable location never raises", True)
except Exception as error:
    check("an unwritable location never raises", False, repr(error))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
