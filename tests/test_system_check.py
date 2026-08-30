#!/usr/bin/env python3
"""
Tests for system_check.py - the single source of truth for environment
health (Wayland/X11). Stdlib-only, machine-independent: anything that
depends on the real machine state is either injected or exercised through
env overrides (WR_FORCE_SESSION, PATH).

    python3 tests/test_system_check.py
"""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import system_check
from system_check import CheckResult

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


def make_shim(directory, name):
    path = Path(directory) / name
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def with_path(directory):
    """Context: temporarily replace PATH."""
    class _Ctx:
        def __enter__(self):
            self.old = os.environ.get("PATH", "")
            os.environ["PATH"] = str(directory)
        def __exit__(self, *a):
            os.environ["PATH"] = self.old
    return _Ctx()


def main():
    # --- get_session_type ---
    os.environ["WR_FORCE_SESSION"] = "wayland"
    check("WR_FORCE_SESSION=wayland override", system_check.get_session_type() == "wayland")
    os.environ["WR_FORCE_SESSION"] = "x11"
    check("WR_FORCE_SESSION=x11 override", system_check.get_session_type() == "x11")
    del os.environ["WR_FORCE_SESSION"]

    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp) / "empty"; empty.mkdir()
        shims = Path(tmp) / "shims"; shims.mkdir()
        for tool in ("wtype", "wl-copy", "wl-paste", "xdotool", "xclip", "paplay"):
            make_shim(shims, tool)

        # --- paste_tool ---
        with with_path(empty):
            r = system_check.check_paste_tool("wayland")
            check("paste_tool wayland missing -> fail+critical",
                  r.status == "fail" and r.critical and "wtype" in (r.fix_cmd or ""),
                  f"got {r}")
            r = system_check.check_paste_tool("x11")
            check("paste_tool x11 missing -> fail mentions xdotool",
                  r.status == "fail" and "xdotool" in (r.fix_cmd or ""), f"got {r}")
        with with_path(shims):
            r = system_check.check_paste_tool("wayland")
            check("paste_tool wayland present -> ok", r.status == "ok", f"got {r}")

        # --- clipboard_tool ---
        with with_path(empty):
            r = system_check.check_clipboard_tool("wayland")
            check("clipboard wayland missing -> fail+critical",
                  r.status == "fail" and r.critical and "wl-clipboard" in (r.fix_cmd or ""),
                  f"got {r}")
        with with_path(shims):
            r = system_check.check_clipboard_tool("wayland")
            check("clipboard wayland wl-copy+wl-paste -> ok", r.status == "ok", f"got {r}")
            r = system_check.check_clipboard_tool("x11")
            check("clipboard x11 xclip -> ok", r.status == "ok", f"got {r}")

        # --- input_group (injected states) ---
        r = system_check.check_input_group("wayland", group_gid=999, process_gids=[999, 4])
        check("input_group member -> ok", r.status == "ok", f"got {r}")
        r = system_check.check_input_group("wayland", group_gid=999, process_gids=[4],
                                           in_group_file=True)
        check("input_group configured but not effective -> warn (relogin)",
              r.status == "warn" and r.critical, f"got {r}")
        r = system_check.check_input_group("wayland", group_gid=999, process_gids=[4],
                                           in_group_file=False)
        check("input_group not member -> fail with usermod hint",
              r.status == "fail" and "usermod" in (r.fix_cmd or ""), f"got {r}")
        r = system_check.check_input_group("x11")
        check("input_group on x11 -> na", r.status == "na", f"got {r}")

        # --- evdev_access (injected paths) ---
        readable = Path(tmp) / "event0"; readable.write_text("")
        r = system_check.check_evdev_access("wayland", device_paths=[str(readable)])
        check("evdev readable device -> ok", r.status == "ok", f"got {r}")
        r = system_check.check_evdev_access("wayland", device_paths=[])
        check("evdev no accessible device -> fail+critical",
              r.status == "fail" and r.critical, f"got {r}")
        r = system_check.check_evdev_access("x11")
        check("evdev on x11 -> na", r.status == "na", f"got {r}")

        # --- overlay ---
        r = system_check.check_overlay("x11")
        check("overlay on x11 -> na", r.status == "na", f"got {r}")
        r = system_check.check_overlay("wayland")
        check("overlay probe on wayland -> valid non-critical status",
              r.status in ("ok", "warn") and not r.critical, f"got {r}")

        # --- run_all / format_cli ---
        os.environ["WR_FORCE_SESSION"] = "wayland"
        results = system_check.run_all()
        del os.environ["WR_FORCE_SESSION"]
        ids = [r.id for r in results]
        expected_ids = ["session", "input_group", "evdev_access", "paste_tool",
                        "clipboard_tool", "overlay", "gpu", "audio_out"]
        check("run_all returns all checks in order", ids == expected_ids, f"got {ids}")
        check("run_all results are CheckResult", all(isinstance(r, CheckResult) for r in results))
        text = system_check.format_cli(results)
        check("format_cli renders every row", all(r.id is not None for r in results) and
              text.count("\n") >= len(results) - 1 and len(text) > 50)

        # --- CLI subprocess ---
        env = dict(os.environ, WR_FORCE_SESSION="wayland", PATH=str(empty))
        proc = subprocess.run([sys.executable, str(REPO_ROOT / "system_check.py")],
                              capture_output=True, text=True, env=env, timeout=30)
        check("CLI exits 1 when critical check fails (no wtype on PATH)",
              proc.returncode == 1, f"rc={proc.returncode} out={proc.stdout[-200:]}")
        check("CLI output mentions the missing paste tool", "wtype" in proc.stdout)

        proc = subprocess.run([sys.executable, str(REPO_ROOT / "system_check.py")],
                              capture_output=True, text=True,
                              env=dict(os.environ), timeout=30)
        check("CLI runs on the real machine without crashing",
              proc.returncode in (0, 1) and len(proc.stdout) > 0,
              f"rc={proc.returncode} err={proc.stderr[-200:]}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
