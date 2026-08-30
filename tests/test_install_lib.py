#!/usr/bin/env python3
"""
Tests for install_lib.sh distro detection.

The installer must pick the right package manager from os-release ID or
ID_LIKE (Omarchy reports ID=omarchy, ID_LIKE=arch), and must never blindly
assume apt on an unknown system.

    python3 tests/test_install_lib.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_LIB = REPO_ROOT / "install_lib.sh"

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


def run_func(func, os_release_path):
    """Source install_lib.sh and run one of its functions against a fixture."""
    result = subprocess.run(
        ["bash", "-c", f'source "{INSTALL_LIB}" && {func} "{os_release_path}"'],
        capture_output=True, text=True, timeout=10,
    )
    return result.stdout.strip(), result.returncode


def write_fixture(tmpdir, content):
    path = Path(tmpdir) / "os-release"
    path.write_text(content)
    return path


def main():
    fixtures = [
        # (name, os-release content, expected manager)
        ("omarchy (ID_LIKE=arch)", 'ID=omarchy\nID_LIKE=arch\n', "pacman"),
        ("cachyos", 'ID=cachyos\nID_LIKE="arch"\n', "pacman"),
        ("arch", 'ID=arch\n', "pacman"),
        ("linuxmint", 'ID=linuxmint\nID_LIKE="ubuntu debian"\n', "apt"),
        ("unknown ID, ID_LIKE=ubuntu debian", 'ID=weirdos\nID_LIKE="ubuntu debian"\n', "apt"),
        ("fedora", 'ID=fedora\n', "dnf"),
        ("nobara (ID_LIKE=fedora)", 'ID=nobara\nID_LIKE="fedora"\n', "dnf"),
        ("opensuse-tumbleweed", 'ID=opensuse-tumbleweed\nID_LIKE="opensuse suse"\n', "zypper"),
        ("quoted ID (Omarchy style quoting)", 'ID="omarchy"\nID_LIKE="arch"\n', "pacman"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        for name, content, expected in fixtures:
            fixture = write_fixture(tmpdir, content)
            out, rc = run_func("detect_pkg_manager", fixture)
            check(f"detect_pkg_manager: {name} -> {expected}", out == expected and rc == 0,
                  f"got {out!r} rc={rc}")

        # Unknown ID with no ID_LIKE: falls back to a binary that exists on
        # this machine - must print a known manager, never crash.
        fixture = write_fixture(tmpdir, 'ID=totallyunknown\n')
        out, rc = run_func("detect_pkg_manager", fixture)
        check("unknown distro falls back to an existing binary",
              out in ("apt", "dnf", "pacman", "zypper"), f"got {out!r}")

        # Missing os-release file: same binary fallback, no crash.
        out, rc = run_func("detect_pkg_manager", Path(tmpdir) / "nonexistent")
        check("missing os-release falls back without crashing",
              out in ("apt", "dnf", "pacman", "zypper", "unknown"), f"got {out!r}")

        # detect_distro_id
        fixture = write_fixture(tmpdir, 'ID=omarchy\nID_LIKE=arch\n')
        out, rc = run_func("detect_distro_id", fixture)
        check("detect_distro_id reads ID", out == "omarchy", f"got {out!r}")

        out, rc = run_func("detect_distro_id", Path(tmpdir) / "nonexistent")
        check("detect_distro_id: missing file -> unknown", out == "unknown", f"got {out!r}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
