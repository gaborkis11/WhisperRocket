#!/usr/bin/env python3
"""
Tests for platform_support/hypr_autostart.py - the marker-delimited
exec-once block WhisperRocket manages in ~/.config/hypr/hyprland.conf
(Hyprland ignores XDG autostart, so the Settings toggle needs this).

    python3 tests/test_hypr_autostart.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from platform_support.hypr_autostart import (
    BLOCK_BEGIN, BLOCK_END, add_autostart_block, remove_autostart_block,
    is_hyprland,
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


USER_CONF = """# my hyprland config
source = ~/.local/share/omarchy/default/hypr/autostart.conf
bind = SUPER, RETURN, exec, alacritty
"""


def main():
    script = "/home/user/WhisperRocket/start.sh"

    # Add to empty text
    out = add_autostart_block("", script)
    check("add to empty text contains markers + exec-once",
          BLOCK_BEGIN in out and BLOCK_END in out and f"exec-once = {script}" in out,
          repr(out))
    check("block ends with newline", out.endswith("\n"))

    # Add preserves user content
    out = add_autostart_block(USER_CONF, script)
    check("user content preserved", USER_CONF.rstrip("\n") in out, repr(out))
    check("block appended after user content",
          out.index("alacritty") < out.index(BLOCK_BEGIN))

    # Idempotent: double add = single block
    twice = add_autostart_block(out, script)
    check("double add keeps a single block",
          twice.count(BLOCK_BEGIN) == 1 and twice.count("exec-once =") == 1,
          repr(twice))

    # Add with a different script path replaces the old one
    moved = add_autostart_block(out, "/new/path/start.sh")
    check("re-add updates the script path",
          "exec-once = /new/path/start.sh" in moved and script not in moved)

    # Remove restores original
    removed = remove_autostart_block(out)
    check("remove restores original user content",
          removed == USER_CONF, repr(removed))

    # Remove without block is a no-op
    check("remove on text without block is a no-op",
          remove_autostart_block(USER_CONF) == USER_CONF)
    check("remove on empty text", remove_autostart_block("") == "")

    # is_hyprland env detection
    saved = {k: os.environ.pop(k, None)
             for k in ("HYPRLAND_INSTANCE_SIGNATURE", "XDG_CURRENT_DESKTOP")}
    try:
        check("is_hyprland false without env", not is_hyprland())
        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = "abc123"
        check("is_hyprland true with instance signature", is_hyprland())
        del os.environ["HYPRLAND_INSTANCE_SIGNATURE"]
        os.environ["XDG_CURRENT_DESKTOP"] = "Hyprland"
        check("is_hyprland true with XDG_CURRENT_DESKTOP", is_hyprland())
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
