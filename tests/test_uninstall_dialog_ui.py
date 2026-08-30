#!/usr/bin/env python3
"""
Offscreen smoke test for the in-app uninstall dialog and its argument
mapping. Self-skips without PySide6.

    venv/bin/python tests/test_uninstall_dialog_ui.py [output_dir]
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import PySide6  # noqa: F401
except ImportError:
    print("SKIP: PySide6 not available (expected in CI)")
    sys.exit(0)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QCheckBox

import qt_helpers

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


COMPONENTS = [
    ("app", "uninstall_comp_app", "", True, True),
    ("config", "uninstall_comp_config", "1.2MB", True, False),
    ("models", "uninstall_comp_models", "3.1GB", True, False),
    ("cuda", "uninstall_comp_cuda", "890MB", True, False),
]


def drive(action, out_png=None):
    def interact():
        dlg = QApplication.activeModalWidget()
        if dlg is None:
            visible = [w for w in QApplication.topLevelWidgets()
                       if isinstance(w, QDialog) and w.isVisible()]
            dlg = visible[0] if visible else None
        if dlg is None:
            return
        if out_png:
            dlg.grab().save(out_png)
        action(dlg)
    QTimer.singleShot(150, interact)


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        tempfile.mkdtemp(prefix="wr_uninst_ui_"))
    print(f"  (screenshots: {out_dir})")
    app = QApplication.instance() or QApplication(sys.argv)

    # Confirm with everything checked
    drive(lambda dlg: dlg.accept(), str(out_dir / "uninstall_dialog_hu.png"))
    choices = qt_helpers.show_uninstall_dialog("hu", COMPONENTS)
    check("confirm returns all-true choices",
          choices == {"app": True, "config": True, "models": True, "cuda": True},
          repr(choices))

    # Cancel returns None
    drive(lambda dlg: dlg.reject())
    choices = qt_helpers.show_uninstall_dialog("en", COMPONENTS)
    check("cancel returns None", choices is None, repr(choices))

    # Uncheck models, confirm
    def uncheck_models(dlg):
        for box in dlg.findChildren(QCheckBox):
            if "model" in box.text().lower() or "3.1GB" in box.text():
                box.setChecked(False)
        dlg.accept()
    drive(uncheck_models)
    choices = qt_helpers.show_uninstall_dialog("en", COMPONENTS)
    check("unchecking models is reflected in choices",
          choices is not None and choices["models"] is False
          and choices["config"] is True, repr(choices))

    # The locked "app" component cannot be unchecked (disabled)
    seen = {}
    def probe_locked(dlg):
        for box in dlg.findChildren(QCheckBox):
            if "launcher" in box.text().lower() or "indító" in box.text().lower():
                seen["enabled"] = box.isEnabled()
        dlg.reject()
    drive(probe_locked)
    qt_helpers.show_uninstall_dialog("en", COMPONENTS)
    check("app-files checkbox is locked", seen.get("enabled") is False,
          repr(seen))

    # Argument mapping (pure function in settings_window)
    from settings_window import build_uninstall_args
    check("all-true -> --auto only",
          build_uninstall_args({"config": True, "models": True, "cuda": True})
          == ["--auto"])
    check("keep models+config flags built",
          build_uninstall_args({"config": False, "models": False, "cuda": True})
          == ["--auto", "--keep-models", "--keep-config"])

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
