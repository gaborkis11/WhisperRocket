#!/usr/bin/env python3
"""
Offscreen smoke test for the Settings window layout: with a large system
font (Omarchy-like) and the model-warning banner visible, widgets must
keep their full height and overflow must scroll - never squeeze text into
slivers (the v1.2.2 Omarchy screenshot bug). Self-skips without PySide6.

    venv/bin/python tests/test_settings_ui.py [output_dir]
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

from PySide6.QtWidgets import QApplication, QScrollArea
from PySide6.QtGui import QFont

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
        tempfile.mkdtemp(prefix="wr_settings_ui_"))
    print(f"  (screenshots: {out_dir})")

    app = QApplication.instance() or QApplication(sys.argv)
    app.setFont(QFont(app.font().family(), 15))  # Omarchy-like large font

    import settings_window as sw
    win = sw.SettingsWindow(apply_phone_endpoint=lambda: None)

    # Force the fresh-machine state: banner visible, small-ish window
    win.model_warning_title.setText("Model Not Downloaded")
    win.model_warning_text.setText(
        "The selected model large-v3 is not downloaded. The app won t work "
        "until you download a model.")
    win.model_warning_frame.setVisible(True)
    win.resize(560, 620)
    win.show()
    app.processEvents()
    win.grab().save(str(out_dir / "settings_bigfont.png"))

    scrolls = win.centralWidget().findChildren(QScrollArea)
    check("Settings window has scroll areas (Settings/Models/AI/Phone tabs)",
          len(scrolls) >= 4, f"found {len(scrolls)}")

    settings_scroll = scrolls[0]
    check("overflowing content is scrollable, not squeezed",
          settings_scroll.verticalScrollBar().maximum() > 0)

    needed = win.fontMetrics().height()
    for name in ("model_warning_text", "model_warning_btn",
                 "hotkey_edit", "record_btn", "autostart_check",
                 "update_check_check"):
        widget = getattr(win, name)
        check(f"{name} keeps full height ({widget.height()}px >= {needed}px)",
              widget.height() >= needed)

    # Model combo labels are translated (Task 2 guard): active-language label
    from translations import t
    label0 = win.model_combo.itemText(win.model_combo.findData("large-v3"))
    check("model combo uses translated wizard label (~3 GB)",
          "~3 GB" in label0 and
          t("wizard_model_large", win.ui_lang).split(" - ")[0] in label0,
          repr(label0))

    win.close()
    # --- AI effort selector ----------------------------------------------------
    combo = getattr(win, "ai_effort_combo", None)
    check("AI tab has an effort selector", combo is not None)
    if combo is not None:
        levels = [combo.itemData(i) for i in range(combo.count())]
        check("effort levels are the CLI's five, low first",
              levels == ["low", "medium", "high", "xhigh", "max"], str(levels))
        check("effort defaults to low", combo.currentData() == "low", str(combo.currentData()))
        win.collect_ai_settings()
        check("collect_ai_settings writes ai_effort", win.config.get("ai_effort") == "low",
              str(win.config.get("ai_effort")))

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
