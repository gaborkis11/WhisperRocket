#!/usr/bin/env python3
"""
WhisperRocket - Environment health checks (single source of truth)

Stdlib-only module used by three consumers:
  - install.sh: end-of-install terminal checklist (``python3 system_check.py``)
  - setup_wizard.py: first-run system-check page
  - whisper_gui.py: startup health dialog on Wayland

Import-time dependencies are standard library only; the GTK/gi probe runs in
a subprocess so this module never loads GTK itself. Session detection honors
the WR_FORCE_SESSION env override (used for testing Wayland behavior on X11).
"""
import glob
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CheckResult:
    id: str
    label_key: str          # translations.py key for the row label
    status: str             # "ok" | "warn" | "fail" | "na"
    detail: str = ""        # short, presentation-ready text
    fix_cmd: Optional[str] = None
    critical: bool = False  # True: the app's core flow breaks without it


def get_session_type() -> str:
    """x11 / wayland / unknown - honors WR_FORCE_SESSION for testing."""
    forced = os.environ.get("WR_FORCE_SESSION", "").lower()
    if forced in ("x11", "wayland"):
        return forced
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session_type in ("x11", "wayland"):
        return session_type
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def get_compositor() -> str:
    """Best-effort compositor/desktop name for the info row."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "Hyprland"
    if os.environ.get("SWAYSOCK"):
        return "Sway"
    return os.environ.get("XDG_CURRENT_DESKTOP", "")


# Same table as install_lib.sh, ported to Python for fix-command hints.
_ID_TO_MANAGER = {
    "ubuntu": "apt", "debian": "apt", "linuxmint": "apt", "pop": "apt",
    "elementary": "apt", "zorin": "apt",
    "fedora": "dnf", "rhel": "dnf", "centos": "dnf", "rocky": "dnf",
    "almalinux": "dnf",
    "arch": "pacman", "archlinux": "pacman", "manjaro": "pacman",
    "endeavouros": "pacman", "garuda": "pacman", "omarchy": "pacman",
    "cachyos": "pacman",
    "suse": "zypper", "sles": "zypper",
}

_INSTALL_TEMPLATES = {
    "apt": "sudo apt install -y {}",
    "dnf": "sudo dnf install -y {}",
    "pacman": "sudo pacman -S --needed {}",
    "zypper": "sudo zypper install -y {}",
}

# Tool -> distro-specific package name where it differs.
_PKG_NAMES = {
    "pacman": {"xdotool": "xdotool", "gtk-layer-shell": "gtk-layer-shell"},
}


def _detect_pkg_manager() -> str:
    os_release = os.environ.get("WR_OS_RELEASE", "/etc/os-release")
    fields = {}
    try:
        with open(os_release) as f:
            for line in f:
                if "=" in line:
                    key, _, value = line.strip().partition("=")
                    fields[key] = value.strip('"')
    except OSError:
        pass
    candidates = [fields.get("ID", "")] + fields.get("ID_LIKE", "").split()
    for candidate in candidates:
        if candidate in _ID_TO_MANAGER:
            return _ID_TO_MANAGER[candidate]
        if candidate.startswith("opensuse"):
            return "zypper"
    for manager in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(manager):
            return manager
    return "apt"


def _pkg_hint(packages) -> str:
    """Build a copy-pasteable install command for this distro."""
    manager = _detect_pkg_manager()
    return _INSTALL_TEMPLATES[manager].format(" ".join(packages))


def check_session(session: str) -> CheckResult:
    compositor = get_compositor()
    detail = session + (f" ({compositor})" if compositor else "")
    return CheckResult("session", "syscheck_session", "ok", detail)


def check_input_group(session: str, group_gid=None, process_gids=None,
                      in_group_file=None) -> CheckResult:
    """Membership in the 'input' group (evdev hotkeys on Wayland).

    Distinguishes "configured but needs relogin" (in /etc/group, not in the
    process's effective groups) from "not configured". The keyword arguments
    exist for test injection; production callers pass only ``session``.
    """
    if session != "wayland":
        return CheckResult("input_group", "syscheck_input_group", "na")

    fix = "sudo usermod -a -G input $USER"
    try:
        if group_gid is None:
            import grp
            entry = grp.getgrnam("input")
            group_gid = entry.gr_gid
            if in_group_file is None:
                username = os.environ.get("USER", "")
                in_group_file = username in entry.gr_mem
        if process_gids is None:
            process_gids = list(os.getgroups())
    except KeyError:
        return CheckResult("input_group", "syscheck_input_group", "fail",
                           "no 'input' group on this system", fix, critical=True)

    if group_gid in process_gids:
        return CheckResult("input_group", "syscheck_input_group", "ok",
                           critical=True)
    if in_group_file:
        return CheckResult("input_group", "syscheck_input_group_relogin", "warn",
                           "log out and back in to activate", critical=True)
    return CheckResult("input_group", "syscheck_input_group", "fail",
                       "", fix, critical=True)


def check_evdev_access(session: str, device_paths=None) -> CheckResult:
    """Can we actually read a keyboard device node? (post-relogin proof)"""
    if session != "wayland":
        return CheckResult("evdev_access", "syscheck_evdev", "na")
    if device_paths is None:
        device_paths = glob.glob("/dev/input/event*")
    readable = [p for p in device_paths if os.access(p, os.R_OK)]
    if readable:
        return CheckResult("evdev_access", "syscheck_evdev", "ok",
                           f"{len(readable)} device(s)", critical=True)
    return CheckResult("evdev_access", "syscheck_evdev", "fail",
                       "no readable /dev/input device (input group + relogin needed)",
                       critical=True)


def check_paste_tool(session: str) -> CheckResult:
    tool = "wtype" if session == "wayland" else "xdotool"
    if shutil.which(tool):
        return CheckResult("paste_tool", "syscheck_paste_tool", "ok", tool,
                           critical=True)
    return CheckResult("paste_tool", "syscheck_paste_tool", "fail",
                       f"{tool} not found", _pkg_hint([tool]), critical=True)


def check_clipboard_tool(session: str) -> CheckResult:
    if session == "wayland":
        if shutil.which("wl-copy") and shutil.which("wl-paste"):
            return CheckResult("clipboard_tool", "syscheck_clipboard_tool", "ok",
                               "wl-clipboard", critical=True)
        return CheckResult("clipboard_tool", "syscheck_clipboard_tool", "fail",
                           "wl-copy/wl-paste not found", _pkg_hint(["wl-clipboard"]),
                           critical=True)
    if shutil.which("xclip") or shutil.which("xsel"):
        return CheckResult("clipboard_tool", "syscheck_clipboard_tool", "ok",
                           critical=True)
    return CheckResult("clipboard_tool", "syscheck_clipboard_tool", "fail",
                       "xclip not found", _pkg_hint(["xclip"]), critical=True)


def check_overlay(session: str) -> CheckResult:
    """GTK Layer Shell availability (focus-free popup). Non-critical: the app
    falls back to a Qt popup, which works but can steal focus on Wayland."""
    if session != "wayland":
        return CheckResult("overlay", "syscheck_overlay", "na")
    probe = ("import gi; gi.require_version('Gtk', '3.0'); "
             "gi.require_version('GtkLayerShell', '0.1')")
    try:
        result = subprocess.run([sys.executable, "-c", probe],
                                capture_output=True, timeout=15)
        if result.returncode == 0:
            return CheckResult("overlay", "syscheck_overlay", "ok",
                               "GTK Layer Shell")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return CheckResult("overlay", "syscheck_overlay", "warn",
                       "Qt fallback popup will be used (may steal focus)",
                       _pkg_hint(["gtk-layer-shell", "python-gobject", "gtk3",
                                  "python-cairo"])
                       if _detect_pkg_manager() == "pacman"
                       else _pkg_hint(["gir1.2-gtklayershell-0.1", "gir1.2-gtk-3.0",
                                       "python3-gi", "python3-gi-cairo"]))


def check_gpu(session: str) -> CheckResult:
    if shutil.which("nvidia-smi"):
        try:
            result = subprocess.run(["nvidia-smi"], capture_output=True, timeout=10)
            if result.returncode == 0:
                return CheckResult("gpu", "syscheck_gpu", "ok", "NVIDIA CUDA")
        except (OSError, subprocess.TimeoutExpired):
            pass
    return CheckResult("gpu", "syscheck_gpu", "warn", "CPU mode (slower)")


def check_audio_out(session: str) -> CheckResult:
    if shutil.which("paplay"):
        return CheckResult("audio_out", "syscheck_audio", "ok", "paplay")
    return CheckResult("audio_out", "syscheck_audio", "warn",
                       "paplay not found - no sound feedback",
                       _pkg_hint(["libpulse"]) if _detect_pkg_manager() == "pacman"
                       else _pkg_hint(["pulseaudio-utils"]))


def run_all(session: Optional[str] = None):
    """Run every check for the given (or detected) session type, in order."""
    if session is None:
        session = get_session_type()
    return [
        check_session(session),
        check_input_group(session),
        check_evdev_access(session),
        check_paste_tool(session),
        check_clipboard_tool(session),
        check_overlay(session),
        check_gpu(session),
        check_audio_out(session),
    ]


_STATUS_MARKS = {
    "ok":   ("\033[0;32m✓\033[0m", "OK "),
    "warn": ("\033[1;33m!\033[0m",      "!  "),
    "fail": ("\033[0;31m✗\033[0m", "FIX"),
    "na":   ("\033[0;90m–\033[0m", "-  "),
}


def format_cli(results, lang: str = "en") -> str:
    """Render the checklist for the terminal (used by install.sh)."""
    try:
        from translations import t
    except ImportError:
        def t(key, _lang, **kw):
            return key
    use_color = sys.stdout.isatty() or os.environ.get("FORCE_COLOR")
    lines = []
    for r in results:
        mark = _STATUS_MARKS[r.status][0 if use_color else 1]
        label = t(r.label_key, lang)
        row = f"  {mark}  {label}"
        if r.detail:
            row += f"  — {r.detail}"
        lines.append(row)
        if r.fix_cmd and r.status in ("warn", "fail"):
            lines.append(f"         $ {r.fix_cmd}")
    return "\n".join(lines)


def main() -> int:
    lang = "en"
    try:
        import json
        import config_paths
        with open(config_paths.get_config_path()) as f:
            lang = json.load(f).get("ui_language", "en")
    except Exception:
        pass
    session = get_session_type()
    results = run_all(session)
    print(f"WhisperRocket system check ({session}):")
    print(format_cli(results, lang))
    if any(r.status == "fail" and r.critical for r in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
