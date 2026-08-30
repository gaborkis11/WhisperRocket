#!/usr/bin/env python3
"""
Tests for the non-interactive uninstall paths: uninstall.sh --auto (bash,
fully sandboxed HOME + fake pgrep/pkill so the real app is never touched)
and appimage_uninstall.remove_components / remove_desktop_entries.

    python3 tests/test_uninstall_auto.py
"""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import appimage_uninstall

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


HYPR_USER_LINES = ("# user config\nbind = SUPER, RETURN, exec, alacritty\n")
HYPR_BLOCK = ("# >>> WhisperRocket autostart >>>\n"
              "exec-once = /x/start.sh\n"
              "# <<< WhisperRocket autostart <<<\n")


def build_home(base):
    home = Path(base) / "home"
    (home / ".local/share/applications").mkdir(parents=True)
    (home / ".local/share/applications/whisperrocket.desktop").write_text("x")
    (home / ".config/autostart").mkdir(parents=True)
    (home / ".config/autostart/whisperrocket.desktop").write_text("x")
    (home / ".config/hypr").mkdir(parents=True)
    (home / ".config/hypr/hyprland.conf").write_text(HYPR_USER_LINES + "\n" + HYPR_BLOCK)
    (home / ".config/whisperrocket").mkdir(parents=True)
    (home / ".config/whisperrocket/config.json").write_text("{}")
    (home / ".cache/huggingface/hub/whisperrocket_models/m1").mkdir(parents=True)
    (home / ".local/share/whisperrocket/cuda_libs").mkdir(parents=True)
    (home / ".bashrc").write_text(
        "alias ll='ls -l'\n"
        "export LD_LIBRARY_PATH=/x/lib:$LD_LIBRARY_PATH # WHISPER_LD_LIBRARY_PATH\n")
    return home


def run_auto(base, extra_args):
    home = build_home(base)
    project = Path(base) / "proj"
    project.mkdir()
    (project / "venv/bin").mkdir(parents=True)
    (project / "uninstall.sh").write_text((REPO_ROOT / "uninstall.sh").read_text())
    shims = Path(base) / "bin"
    shims.mkdir()
    for name, body in (("pgrep", "exit 1\n"), ("pkill", "exit 0\n")):
        p = shims / name
        p.write_text("#!/bin/bash\n" + body)
        p.chmod(p.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ, HOME=str(home), PATH=f"{shims}:{os.environ['PATH']}")
    result = subprocess.run(["bash", "uninstall.sh", "--auto"] + extra_args,
                            cwd=project, env=env, capture_output=True,
                            text=True, timeout=60)
    return home, project, result


def main():
    # --- bash --auto: full ---
    with tempfile.TemporaryDirectory() as tmp:
        home, project, result = run_auto(tmp, [])
        check("--auto exits 0", result.returncode == 0, result.stderr[-200:])
        check("launcher removed",
              not (home / ".local/share/applications/whisperrocket.desktop").exists())
        check("autostart entry removed",
              not (home / ".config/autostart/whisperrocket.desktop").exists())
        hypr = (home / ".config/hypr/hyprland.conf").read_text()
        check("hyprland block removed, user lines intact",
              ">>> WhisperRocket" not in hypr and "alacritty" in hypr, repr(hypr))
        check("venv removed", not (project / "venv").exists())
        check("config removed", not (home / ".config/whisperrocket").exists())
        check("models removed",
              not (home / ".cache/huggingface/hub/whisperrocket_models").exists())
        check("cuda dir removed", not (home / ".local/share/whisperrocket").exists())
        bashrc = (home / ".bashrc").read_text()
        check("bashrc CUDA line removed, aliases intact",
              "WHISPER_LD_LIBRARY_PATH" not in bashrc and "alias ll" in bashrc,
              repr(bashrc))

    # --- bash --auto --keep-models --keep-config ---
    with tempfile.TemporaryDirectory() as tmp:
        home, project, result = run_auto(tmp, ["--keep-models", "--keep-config"])
        check("keep-flags exit 0", result.returncode == 0, result.stderr[-200:])
        check("--keep-models keeps the models dir",
              (home / ".cache/huggingface/hub/whisperrocket_models").exists())
        check("--keep-config keeps the config dir",
              (home / ".config/whisperrocket").exists())
        check("venv still removed with keep-flags",
              not (project / "venv").exists())

    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(["bash", str(REPO_ROOT / "uninstall.sh"), "--bogus"],
                                capture_output=True, text=True, timeout=10)
        check("unknown flag rejected", result.returncode == 1)

    # --- python: remove_components / remove_desktop_entries ---
    with tempfile.TemporaryDirectory() as tmp:
        home = build_home(tmp)
        removed = appimage_uninstall.remove_components(models=False, home=home)
        check("remove_components honors models=False",
              (home / ".cache/huggingface/hub/whisperrocket_models").exists()
              and not (home / ".config/whisperrocket").exists()
              and not (home / ".local/share/whisperrocket").exists()
              and len(removed) == 2, f"removed={removed}")

        removed = appimage_uninstall.remove_desktop_entries(home=home)
        hypr = (home / ".config/hypr/hyprland.conf").read_text()
        check("remove_desktop_entries cleans launcher+autostart+hypr block",
              not (home / ".local/share/applications/whisperrocket.desktop").exists()
              and not (home / ".config/autostart/whisperrocket.desktop").exists()
              and ">>> WhisperRocket" not in hypr and "alacritty" in hypr,
              f"removed={removed}")

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
