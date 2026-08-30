#!/usr/bin/env python3
"""
Tests for update_checker.py - GitHub release check, bilingual cumulative
release notes, auto-check throttling and the AppImage download/replace
helper. Stdlib-only; every network call is injected.

    python3 tests/test_update_checker.py
"""
import os
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import update_checker
from update_checker import (
    UpdateInfo, parse_version, check_for_update, should_auto_check,
    download_and_replace,
)

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


def release_json(tag="v1.3.0", with_asset=True, body="release body text"):
    assets = []
    if with_asset:
        assets.append({"name": "WhisperRocket-x86_64.AppImage",
                       "browser_download_url": "https://example.com/wr.AppImage",
                       "size": 12345})
        assets.append({"name": "WhisperRocket-x86_64.AppImage.zsync",
                       "browser_download_url": "https://example.com/wr.zsync",
                       "size": 100})
    return {"tag_name": tag, "html_url": "https://example.com/release",
            "body": body, "assets": assets}


def notes_json():
    return {"versions": [
        {"version": "1.3.0", "date": "2026-09-01",
         "notes": {"en": ["big feature"], "hu": ["nagy funkció"]}},
        {"version": "1.2.2", "date": "2026-08-30",
         "notes": {"en": ["update checker"], "hu": ["frissítéskereső"]}},
        {"version": "1.2.1", "date": "2026-08-30",
         "notes": {"en": ["omarchy support"], "hu": ["omarchy támogatás"]}},
    ]}


def main():
    # --- parse_version ---
    check("parse v-prefixed", parse_version("v1.2.2") == (1, 2, 2))
    check("parse two-part pads to three", parse_version("1.2") == (1, 2, 0))
    check("parse garbage parts -> zeros", parse_version("v1.x.beta") == (1, 0, 0))
    check("parse empty never raises", parse_version("") == (0, 0, 0))

    # --- check_for_update ---
    info = check_for_update("1.2.2", "en", fetcher=release_json,
                            notes_fetcher=notes_json)
    check("newer detected", info.is_newer and info.latest == "1.3.0"
          and info.error is None, f"got {info}")
    check("asset url + size picked",
          info.asset_url == "https://example.com/wr.AppImage"
          and info.asset_size == 12345, f"got {info.asset_url}")
    check("cumulative notes exclude current and older",
          "big feature" in info.notes_text and "update checker" not in
          info.notes_text and "omarchy" not in info.notes_text,
          repr(info.notes_text))

    info = check_for_update("1.2.0", "hu", fetcher=release_json,
                            notes_fetcher=notes_json)
    check("hungarian cumulative notes span skipped versions",
          "nagy funkció" in info.notes_text and "frissítéskereső" in
          info.notes_text and "omarchy támogatás" in info.notes_text,
          repr(info.notes_text))
    check("notes carry version headings", "1.3.0" in info.notes_text
          and "1.2.1" in info.notes_text)

    info = check_for_update("1.3.0", "en", fetcher=release_json,
                            notes_fetcher=notes_json)
    check("equal version -> not newer", not info.is_newer and info.error is None)
    info = check_for_update("2.0.0", "en", fetcher=release_json,
                            notes_fetcher=notes_json)
    check("older release -> not newer", not info.is_newer)

    info = check_for_update("1.2.2", "en",
                            fetcher=lambda: release_json(with_asset=False),
                            notes_fetcher=notes_json)
    check("missing asset: still newer, asset_url None",
          info.is_newer and info.asset_url is None)

    def boom():
        raise OSError("no network")
    info = check_for_update("1.2.2", "en", fetcher=boom, notes_fetcher=notes_json)
    check("API failure -> error set, not newer",
          info.error is not None and not info.is_newer)

    info = check_for_update("1.2.2", "en", fetcher=release_json,
                            notes_fetcher=boom)
    check("notes failure alone is not an error - release body fallback",
          info.is_newer and info.error is None
          and "release body text" in info.notes_text, repr(info.notes_text))

    def notes_no_hu():
        return {"versions": [{"version": "1.3.0", "date": "2026-09-01",
                              "notes": {"en": ["english only"]}}]}
    info = check_for_update("1.2.2", "hu", fetcher=release_json,
                            notes_fetcher=notes_no_hu)
    check("hu missing -> falls back to en notes",
          "english only" in info.notes_text, repr(info.notes_text))

    # --- should_auto_check ---
    now = 1_000_000_000
    check("auto: disabled", not should_auto_check(
        {"update_check_enabled": False}, now=now))
    check("auto: fresh timestamp blocks", not should_auto_check(
        {"update_last_check": now - 100}, now=now))
    check("auto: stale timestamp allows", should_auto_check(
        {"update_last_check": now - 90000}, now=now))
    check("auto: missing keys allow", should_auto_check({}, now=now))

    # --- download_and_replace ---
    payload = b"NEW-APPIMAGE-BYTES"

    def fake_downloader(url, dest_path, progress_cb, cancel_flag):
        with open(dest_path, "wb") as f:
            f.write(payload)
        progress_cb(len(payload), len(payload))

    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "WhisperRocket.AppImage"
        target.write_bytes(b"OLD")
        err = download_and_replace("https://x", len(payload), str(target),
                                   lambda d, t: None, lambda: False,
                                   downloader=fake_downloader)
        check("replace success", err is None and
              target.read_bytes() == payload, f"err={err}")
        check("replaced file is executable",
              target.stat().st_mode & stat.S_IXUSR)

        target.write_bytes(b"OLD")
        err = download_and_replace("https://x", 999999, str(target),
                                   lambda d, t: None, lambda: False,
                                   downloader=fake_downloader)
        check("size mismatch -> error, original intact",
              err is not None and target.read_bytes() == b"OLD")
        check("size mismatch leaves no .new orphan",
              not (Path(tmp) / "WhisperRocket.AppImage.new").exists())

        def cancelling_downloader(url, dest_path, progress_cb, cancel_flag):
            with open(dest_path, "wb") as f:
                f.write(b"partial")
            raise update_checker.DownloadCancelled()
        target.write_bytes(b"OLD")
        err = download_and_replace("https://x", len(payload), str(target),
                                   lambda d, t: None, lambda: True,
                                   downloader=cancelling_downloader)
        check("cancel -> error, original intact",
              err is not None and target.read_bytes() == b"OLD")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
