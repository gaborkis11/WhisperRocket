#!/usr/bin/env python3
"""
Offscreen smoke test for the update dialogs (qt_helpers.show_update_dialog,
show_source_update_hint). Self-skips without PySide6 (CI has no Qt).

    venv/bin/python tests/test_update_dialog_ui.py [output_dir]
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
from PySide6.QtWidgets import QApplication, QDialog

import qt_helpers
from update_checker import UpdateInfo

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


INFO = UpdateInfo(
    current="1.2.1", latest="1.2.2", is_newer=True,
    release_url="https://example.com/release",
    asset_url="https://example.com/wr.AppImage", asset_size=100,
    notes_text=("v1.2.2 — 2026-08-30\n"
                "  • Az app mostantól észreveszi az új verziókat\n"
                "  • Az AppImage magát frissíti\n\n"
                "v1.2.1 — 2026-08-30\n"
                "  • Omarchy / Hyprland támogatás"))


def drive_dialog(action, out_png=None):
    """Schedule interaction with the modal dialog, then run it."""
    def interact():
        dlg = QApplication.activeModalWidget()
        if dlg is None:
            widgets = [w for w in QApplication.topLevelWidgets()
                       if isinstance(w, QDialog) and w.isVisible()]
            dlg = widgets[0] if widgets else None
        if dlg is None:
            return
        if out_png:
            dlg.grab().save(out_png)
        action(dlg)
    QTimer.singleShot(150, interact)


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        tempfile.mkdtemp(prefix="wr_upd_ui_"))
    print(f"  (screenshots: {out_dir})")
    app = QApplication.instance() or QApplication(sys.argv)

    # Accept -> ("update", False)
    drive_dialog(lambda dlg: dlg.accept(),
                 str(out_dir / "update_dialog_hu.png"))
    choice, disable = qt_helpers.show_update_dialog(INFO, "hu")
    check("accept returns update + no disable",
          choice == "update" and disable is False, f"got {choice}, {disable}")

    # Tick the checkbox, reject -> ("later", True)
    def tick_and_reject(dlg):
        from PySide6.QtWidgets import QCheckBox
        boxes = dlg.findChildren(QCheckBox)
        if boxes:
            boxes[0].setChecked(True)
        dlg.reject()
    drive_dialog(tick_and_reject)
    choice, disable = qt_helpers.show_update_dialog(INFO, "en")
    check("reject with checkbox returns later + disable",
          choice == "later" and disable is True, f"got {choice}, {disable}")

    # Notes text is actually rendered
    rendered = {}
    def read_notes(dlg):
        from PySide6.QtWidgets import QTextEdit
        edits = dlg.findChildren(QTextEdit)
        rendered["text"] = edits[0].toPlainText() if edits else ""
        dlg.reject()
    drive_dialog(read_notes)
    qt_helpers.show_update_dialog(INFO, "hu")
    check("dialog renders cumulative notes",
          "Omarchy" in rendered.get("text", "") and
          "1.2.2" in rendered.get("text", ""), repr(rendered.get("text", ""))[:80])

    # Source-install hint dialog renders the git command
    seen = {}
    def read_hint(dlg):
        from PySide6.QtWidgets import QLineEdit
        fields = dlg.findChildren(QLineEdit)
        seen["cmd"] = fields[0].text() if fields else ""
        dlg.accept()
    drive_dialog(read_hint, str(out_dir / "source_hint_hu.png"))
    qt_helpers.show_source_update_hint(INFO, "hu")
    check("source hint shows git pull command",
          seen.get("cmd", "").startswith("git -C ") and
          seen.get("cmd", "").endswith(" pull"), repr(seen.get("cmd")))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
