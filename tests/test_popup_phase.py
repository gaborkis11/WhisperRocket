#!/usr/bin/env python3
"""
The processing popup's phase row: local transcription first, AI cleanup when
the model is called, and the popup never changes size between the two.

Three parts, each self-skipping when its toolkit is missing:
  1. popup_phases (stdlib): pools, lengths, labels present in both languages
  2. the Qt popup, offscreen: state gating, size, both phases painted
  3. the GTK overlay's icon, drawn on a bare cairo surface (no display needed)

    python3 tests/test_popup_phase.py [output_dir]   # PNGs of both phases
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import popup_phases  # noqa: E402
from translations import TRANSLATIONS  # noqa: E402

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


out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else None

# --- 1. the shared phase data ------------------------------------------------
check("two phases, local first", popup_phases.PHASES == ("stt", "ai"))
for phase in popup_phases.PHASES:
    pool = popup_phases.MESSAGES[phase]
    check(f"{phase}: a real pool", len(pool) >= 10, str(len(pool)))
    too_long = [m for m in pool if len(m) > popup_phases.MAX_MESSAGE_CHARS]
    check(f"{phase}: every joke fits the popup", not too_long, str(too_long))
    check(f"{phase}: every joke trails off like the old ones",
          all(m.endswith("...") for m in pool), str([m for m in pool if not m.endswith("...")]))
    for lang in ("en", "hu"):
        key = popup_phases.LABEL_KEYS[phase]
        check(f"{phase}: label key {key} exists in {lang}",
              bool(TRANSLATIONS.get(lang, {}).get(key)), key)
    check(f"{phase}: accent is an RGB triple",
          len(popup_phases.ACCENT_RGB[phase]) == 3 and all(0 <= c <= 255 for c in popup_phases.ACCENT_RGB[phase]))

shared = set(popup_phases.MESSAGES["stt"]) & set(popup_phases.MESSAGES["ai"])
check("no joke belongs to both phases", not shared, str(shared))
check("the AI pool talks about cleaning, not listening",
      not any("transcrib" in m.lower() for m in popup_phases.MESSAGES["ai"]))
check("unknown phase falls back to local", popup_phases.normalize("nonsense") == "stt")
check("None falls back to local", popup_phases.normalize(None) == "stt")
picks = {popup_phases.pick_message("ai", previous="Polishing your prose...") for _ in range(60)}
check("pick_message never repeats the joke on screen", "Polishing your prose..." not in picks)
check("pick_message stays inside the phase's pool",
      picks <= set(popup_phases.MESSAGES["ai"]), str(picks - set(popup_phases.MESSAGES["ai"])))

# --- 2. the Qt popup, offscreen ----------------------------------------------
try:
    import PySide6  # noqa: F401
    have_qt = True
except ImportError:
    have_qt = False
    print("  SKIP  Qt popup checks (PySide6 not available)")

if have_qt:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from queue import Queue
    from PySide6.QtWidgets import QApplication
    from popup_window import RecordingPopup, PopupManager, PopupState

    app = QApplication.instance() or QApplication(sys.argv)
    popup = RecordingPopup(Queue(), "alt+s", 5, "en")

    popup.show_phase("ai")
    check("qt: a phase before processing is ignored", popup.phase == "stt")

    popup.show_popup()
    size_recording = (popup.width(), popup.height())
    popup.show_processing()
    size_stt = (popup.width(), popup.height())
    check("qt: processing starts in the local phase", popup.phase == "stt")
    check("qt: the joke belongs to the local pool",
          popup.current_message in popup_phases.MESSAGES["stt"], popup.current_message)
    check("qt: processing keeps the recording window's size",
          size_stt == size_recording == (popup.base_width, popup.base_height), str(size_stt))
    image_stt = popup.grab()
    check("qt: the local phase paints", not image_stt.isNull())

    popup.show_phase("ai")
    size_ai = (popup.width(), popup.height())
    check("qt: switches to the AI phase", popup.phase == "ai")
    check("qt: the joke switches pools too",
          popup.current_message in popup_phases.MESSAGES["ai"], popup.current_message)
    check("qt: the window does not change size between phases", size_ai == size_stt, str(size_ai))
    check("qt: the message timer keeps running", popup.message_timer.isActive())
    image_ai = popup.grab()
    check("qt: the AI phase paints", not image_ai.isNull())
    check("qt: the two phases look different", image_ai.toImage() != image_stt.toImage())

    popup.show_phase("garbage")
    check("qt: an unknown phase falls back to local", popup.phase == "stt")

    popup.show_phase("ai")
    popup.show_text("Szia! Kész.")
    check("qt: show_text ends processing as before", popup.state == PopupState.TEXT_PREVIEW)
    popup.show_phase("stt")
    check("qt: a phase after the text is up is ignored", popup.phase == "ai")
    check("qt: text preview keeps its own height", popup.height() == popup.preview_height)

    popup.show_processing()
    check("qt: a new dictation starts local again", popup.phase == "stt")
    popup.hide_popup()
    check("qt: hiding stops the joke timer", not popup.message_timer.isActive())

    manager = PopupManager(Queue(), "alt+s", 5, "en")
    manager.request_show_phase.emit("ai")
    check("qt: the manager survives a phase with no popup", manager._popup is None)
    manager.request_show_popup.emit()
    manager.request_show_processing.emit()
    manager.request_show_phase.emit("ai")
    app.processEvents()
    check("qt: the manager forwards the phase to its popup",
          manager._popup is not None and manager._popup.phase == "ai",
          str(manager._popup and manager._popup.phase))
    manager.request_hide_popup.emit()

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        image_stt.save(str(out_dir / "popup_phase_stt.png"))
        image_ai.save(str(out_dir / "popup_phase_ai.png"))
        print(f"  saved {out_dir}/popup_phase_stt.png and popup_phase_ai.png")

# --- 3. the overlay's icon on a bare cairo surface (no GTK, no display) ---------
try:
    import cairo
    have_cairo = True
except ImportError:
    have_cairo = False
    print("  SKIP  cairo icon checks (pycairo not available)")

if have_cairo:
    check("the cairo line-cap constant matches the library",
          popup_phases._CAIRO_LINE_CAP_ROUND == cairo.LINE_CAP_ROUND)
    for phase in popup_phases.PHASES:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                     popup_phases.ICON_WIDTH * 4, popup_phases.ICON_HEIGHT * 4)
        cr = cairo.Context(surface)
        cr.scale(4, 4)
        try:
            for frame in (0, 15, 30, 45):
                popup_phases.draw_icon_cairo(cr, phase, frame)
            painted = any(surface.get_data()[3::4])  # any alpha at all
            check(f"cairo: the {phase} icon draws on a plain surface", painted)
        except Exception as e:
            check(f"cairo: the {phase} icon draws on a plain surface", False, f"{type(e).__name__}: {e}")
        if out_dir:
            surface.write_to_png(str(out_dir / f"overlay_icon_{phase}.png"))

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
