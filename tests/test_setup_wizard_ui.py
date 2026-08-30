#!/usr/bin/env python3
"""
Offscreen smoke test for the setup wizard's system-check page.

Runs only where PySide6 is installed (the app venv); in CI it prints SKIP
and exits 0 - CI has no Qt. Simulates a fresh Omarchy machine (Wayland,
not in input group yet, wtype/wl-clipboard missing) and verifies the page
flow: check page first, re-check rebuilds, Continue reaches model page.
Saves PNGs of both pages next to the repo for visual review.

    venv/bin/python tests/test_setup_wizard_ui.py [output_dir]
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import PySide6  # noqa: F401
except ImportError:
    print("SKIP: PySide6 not available (expected in CI)")
    sys.exit(0)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["WR_FORCE_SESSION"] = "wayland"

from PySide6.QtWidgets import QApplication

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


FRESH_OMARCHY = [
    CheckResult("session", "syscheck_session", "ok", "wayland (Hyprland)"),
    CheckResult("input_group", "syscheck_input_group_relogin", "warn",
                "log out and back in to activate", critical=True),
    CheckResult("evdev_access", "syscheck_evdev", "fail",
                "no readable /dev/input device", critical=True),
    CheckResult("paste_tool", "syscheck_paste_tool", "fail", "wtype not found",
                "sudo pacman -S --needed wtype", critical=True),
    CheckResult("clipboard_tool", "syscheck_clipboard_tool", "fail",
                "wl-copy/wl-paste not found",
                "sudo pacman -S --needed wl-clipboard", critical=True),
    CheckResult("overlay", "syscheck_overlay", "warn", "Qt fallback popup"),
    CheckResult("gpu", "syscheck_gpu", "ok", "NVIDIA CUDA"),
    CheckResult("audio_out", "syscheck_audio", "ok", "paplay"),
]

ALL_OK = [CheckResult(r.id, r.label_key.replace("_relogin", ""), "ok", "",
                      critical=r.critical) for r in FRESH_OMARCHY]


def main():
    import tempfile
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        os.environ.get("WR_UI_TEST_OUT") or tempfile.mkdtemp(prefix="wr_ui_"))
    print(f"  (screenshots: {out_dir})")

    fake_state = {"results": FRESH_OMARCHY}
    real_run_all = system_check.run_all
    system_check.run_all = lambda session=None: fake_state["results"]
    try:
        import setup_wizard
        app = QApplication.instance() or QApplication(sys.argv)
        wizard = setup_wizard.SetupWizard()

        check("check page shown first on wayland",
              wizard.stack.currentWidget() is wizard.page_check)
        check("continue button says 'continue anyway' while criticals fail",
              wizard.continue_btn.text() != "" and
              wizard.continue_btn.text() == setup_wizard.t(
                  "wizard_syscheck_continue_anyway", wizard.lang))

        wizard.resize(450, 560)
        wizard.grab().save(str(out_dir / "wizard_check_page.png"))

        # Simulate the user fixing everything, then pressing Re-check
        fake_state["results"] = ALL_OK
        wizard.recheck_btn.click()
        check("re-check switches footer to all-ok",
              wizard.continue_btn.text() == setup_wizard.t(
                  "wizard_syscheck_continue", wizard.lang))

        wizard.grab().save(str(out_dir / "wizard_check_page_ok.png"))

        # Continue lands on the model page
        wizard.continue_btn.click()
        check("continue reaches the model page",
              wizard.stack.currentWidget() is wizard.page_model)
        wizard.grab().save(str(out_dir / "wizard_model_page.png"))

        # X11 with everything fine: wizard must start on the model page
        os.environ["WR_FORCE_SESSION"] = "x11"
        wizard2 = setup_wizard.SetupWizard()
        check("x11 all-ok starts on model page",
              wizard2.stack.currentWidget() is wizard2.page_model)
    finally:
        system_check.run_all = real_run_all
        os.environ["WR_FORCE_SESSION"] = "wayland"

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
