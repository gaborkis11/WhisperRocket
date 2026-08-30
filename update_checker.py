#!/usr/bin/env python3
"""
WhisperRocket - Update checking and AppImage self-update

Privacy contract: nothing here runs on its own. The startup probe in
whisper_gui.py calls check_for_update() at most once per 24h and only while
the "Check for updates at startup" setting is on; the About window button
calls it on click. The check is one unauthenticated GitHub API request that
sends nothing about the user.

Release notes come from updates.json on the repo's main branch - a bilingual
(EN/HU) per-version changelog - so the dialog can show what changed in the
user's language, cumulatively for every version they skipped. The GitHub
release body is the English-only fallback. tests/test_updates_json.py keeps
the file well-formed and in sync with APP_VERSION.

Stdlib-only at import time (CI runs these tests with no pip installs);
`requests` is imported lazily inside the download path only.
"""
import json
import os
import stat
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

REPO_SLUG = "gaborkis11/WhisperRocket"
API_LATEST_URL = f"https://api.github.com/repos/{REPO_SLUG}/releases/latest"
NOTES_URL = f"https://raw.githubusercontent.com/{REPO_SLUG}/main/updates.json"
USER_AGENT = "WhisperRocket-update-check"
AUTO_CHECK_INTERVAL = 86400  # seconds - at most one automatic check per day


class DownloadCancelled(Exception):
    pass


@dataclass
class UpdateInfo:
    current: str
    latest: str = ""
    is_newer: bool = False
    release_url: str = ""
    asset_url: Optional[str] = None
    asset_size: Optional[int] = None
    notes_text: str = ""
    error: Optional[str] = None


def parse_version(text) -> tuple:
    """'v1.2.2' / '1.2' -> (1,2,2) / (1,2,0). Garbage parts become 0;
    never raises."""
    parts = []
    for part in str(text or "").lstrip("v").split("."):
        parts.append(int(part) if part.isdigit() else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _http_json(url: str):
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _fetch_latest_release():
    return _http_json(API_LATEST_URL)


def _fetch_notes():
    return _http_json(NOTES_URL)


def _render_notes(notes_data, current_version: str, lang: str) -> str:
    """Every updates.json entry newer than current_version, newest first,
    in the requested language (falling back to English per entry)."""
    current = parse_version(current_version)
    blocks = []
    for entry in notes_data.get("versions", []):
        if parse_version(entry.get("version")) <= current:
            continue
        notes = entry.get("notes", {})
        lines = notes.get(lang) or notes.get("en") or []
        if not lines:
            continue
        heading = f"v{entry.get('version')} — {entry.get('date', '')}".rstrip(" —")
        blocks.append(heading + "\n" + "\n".join(f"  • {line}" for line in lines))
    return "\n\n".join(blocks)


def check_for_update(current_version: str, lang: str = "en",
                     fetcher=None, notes_fetcher=None) -> UpdateInfo:
    """Compare current_version to the latest GitHub release. Network and
    parse failures land in .error; a notes failure alone falls back to the
    release body and is not an error."""
    info = UpdateInfo(current=current_version)
    try:
        release = (fetcher or _fetch_latest_release)()
        info.latest = str(release.get("tag_name", "")).lstrip("v")
        info.release_url = release.get("html_url", "")
        info.is_newer = parse_version(info.latest) > parse_version(current_version)
        for asset in release.get("assets", []):
            if str(asset.get("name", "")).endswith(".AppImage"):
                info.asset_url = asset.get("browser_download_url")
                info.asset_size = asset.get("size")
                break
        if info.is_newer:
            try:
                notes_data = (notes_fetcher or _fetch_notes)()
                info.notes_text = _render_notes(notes_data, current_version, lang)
            except Exception:
                info.notes_text = ""
            if not info.notes_text:
                info.notes_text = str(release.get("body", "") or "")
    except Exception as error:
        info.error = str(error)
        info.is_newer = False
    return info


def should_auto_check(config: dict, now=None) -> bool:
    """True when the startup check may run: the setting is on (default) and
    the last check is older than AUTO_CHECK_INTERVAL."""
    if config.get("update_check_enabled", True) is False:
        return False
    now = time.time() if now is None else now
    last = config.get("update_last_check", 0) or 0
    return (now - last) >= AUTO_CHECK_INTERVAL


def _requests_downloader(url, dest_path, progress_cb, cancel_flag):
    """Streaming download with cancel support (pattern: download_manager.py)."""
    import requests  # lazy: keeps this module stdlib-only at import time
    response = requests.get(url, stream=True, timeout=30,
                            headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))
    done = 0
    with open(dest_path, "wb") as output:
        for chunk in response.iter_content(chunk_size=1024 * 256):
            if cancel_flag():
                raise DownloadCancelled()
            if chunk:
                output.write(chunk)
                done += len(chunk)
                progress_cb(done, total)


def download_and_replace(asset_url: str, asset_size, target_path: str,
                         progress_cb, cancel_flag,
                         downloader=None) -> Optional[str]:
    """Download the new AppImage next to the old one and swap atomically.
    Returns an error string, or None on success. The original file is left
    untouched on any failure."""
    new_path = target_path + ".new"
    try:
        (downloader or _requests_downloader)(asset_url, new_path,
                                             progress_cb, cancel_flag)
        actual = os.path.getsize(new_path)
        if asset_size and actual != asset_size:
            raise ValueError(f"size mismatch: got {actual}, expected {asset_size}")
        os.chmod(new_path, os.stat(new_path).st_mode
                 | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(new_path, target_path)
        return None
    except DownloadCancelled:
        return "cancelled"
    except Exception as error:
        return str(error)
    finally:
        if os.path.exists(new_path):
            try:
                os.remove(new_path)
            except OSError:
                pass
