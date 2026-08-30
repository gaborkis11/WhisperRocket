"""
WhisperRocket - Hyprland autostart via a managed config block

Hyprland does not process XDG autostart (~/.config/autostart), so on
Hyprland-based systems (e.g. Omarchy) the Settings autostart toggle also
manages a clearly marked exec-once block in ~/.config/hypr/hyprland.conf.
The block is delimited by BEGIN/END markers so it can be added, replaced
and removed idempotently without touching the user's own config lines.
uninstall.sh removes the same block with sed on the identical markers.

Pure text functions - no file I/O here - so the logic is unit-testable
(tests/test_hypr_autostart.py).
"""
import os

BLOCK_BEGIN = "# >>> WhisperRocket autostart >>>"
BLOCK_END = "# <<< WhisperRocket autostart <<<"


def is_hyprland() -> bool:
    """True when running inside a Hyprland session."""
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return True
    return "hyprland" in os.environ.get("XDG_CURRENT_DESKTOP", "").lower()


def remove_autostart_block(conf_text: str) -> str:
    """Return conf_text with the managed block (and its markers) removed."""
    if BLOCK_BEGIN not in conf_text:
        return conf_text
    lines = conf_text.splitlines(keepends=True)
    result = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped == BLOCK_BEGIN:
            inside = True
            continue
        if stripped == BLOCK_END:
            inside = False
            continue
        if not inside:
            result.append(line)
    text = "".join(result)
    # Drop the blank line the add step placed before the block
    while text.endswith("\n\n"):
        text = text[:-1]
    return text


def add_autostart_block(conf_text: str, start_script: str) -> str:
    """Return conf_text with the managed block appended (replacing any
    previous one), pointing exec-once at start_script."""
    text = remove_autostart_block(conf_text)
    if text and not text.endswith("\n"):
        text += "\n"
    if text:
        text += "\n"
    return (f"{text}{BLOCK_BEGIN}\n"
            f"exec-once = {start_script}\n"
            f"{BLOCK_END}\n")
