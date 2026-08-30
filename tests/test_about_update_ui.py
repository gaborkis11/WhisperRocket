#!/usr/bin/env python3
"""
Offscreen smoke test for the About window's check-for-updates flow.
Self-skips without PySide6. The result handler is driven directly with
fabricated UpdateInfo values; whisper_gui is replaced with a stub so the
heavy app module never loads.

    venv/bin/python tests/test_about_update_ui.py [output_dir]
"""
import os
import sys
import tempfile
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import PySide6  # noqa: F401
except ImportError:
    print("SKIP: PySide6 not available (expected in CI)")
    sys.exit(0)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

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


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(
        tempfile.mkdtemp(prefix="wr_about_ui_"))
    print(f"  (screenshots: {out_dir})")

    # Stub whisper_gui BEFORE about_window's handler imports it
    calls = {"perform": [], "save": []}
    stub = types.SimpleNamespace(
        perform_update=lambda info: calls["perform"].append(info),
        save_config_value=lambda k, v: calls["save"].append((k, v)))
    sys.modules["whisper_gui"] = stub

    import about_window
    import qt_helpers
    from update_checker import UpdateInfo
    from translations import t

    app = QApplication.instance() or QApplication(sys.argv)
    win = about_window.AboutWindow()
    lang = win.ui_lang

    check("update button present with translated label",
          win.update_btn.text() == t("update_check_btn", lang))

    # Error outcome
    win._on_update_result(UpdateInfo(current="1.2.1", error="no network"))
    check("error renders update_failed",
          win.update_result.isVisibleTo(win) is not None and
          t("update_failed", lang) in win.update_result.text(),
          win.update_result.text())

    # Up-to-date outcome
    win._on_update_result(UpdateInfo(current="1.2.1", latest="1.2.1",
                                     is_newer=False))
    check("up-to-date renders update_uptodate",
          t("update_uptodate", lang) in win.update_result.text(),
          win.update_result.text())

    # Newer outcome -> shared dialog invoked, then perform_update on "update"
    dialog_calls = []
    real_dialog = qt_helpers.show_update_dialog
    qt_helpers.show_update_dialog = \
        lambda info, lng, parent=None: (dialog_calls.append((info, lng)),
                                        ("update", True))[1]
    try:
        newer = UpdateInfo(current="1.2.1", latest="1.2.2", is_newer=True,
                           release_url="https://example.com",
                           notes_text="v1.2.2\n  • something new")
        win._on_update_result(newer)
    finally:
        qt_helpers.show_update_dialog = real_dialog

    check("newer invokes the shared update dialog",
          len(dialog_calls) == 1 and dialog_calls[0][1] == lang)
    check("'update' choice hands off to whisper_gui.perform_update",
          calls["perform"] == [newer])
    check("disable-auto persists the setting",
          calls["save"] == [("update_check_enabled", False)])

    win.resize(340, 480)
    win.grab().save(str(out_dir / "about_window.png"))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
