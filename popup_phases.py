#!/usr/bin/env python3
"""
WhisperRocket - The two phases of a dictation, as the popup tells them apart.

A dictation runs in two very different stages: the local Whisper model turns
the audio into text, then - only when AI cleanup is on - the Claude CLI tidies
that text. The two take a similar number of seconds, so a popup that just says
"processing" leaves the user guessing which half they are waiting for. Both
popups (Qt on X11, GTK on Wayland) draw a small phase row under the rocket
from this one module, so they never disagree about words, colours or jokes.

Stdlib only: the tests run without Qt or GTK, and whisper_gui imports it to
name the phase it reports.
"""
import random

PHASE_STT = "stt"   # the local speech-to-text model, every dictation
PHASE_AI = "ai"     # the AI cleanup, only while it is switched on

PHASES = (PHASE_STT, PHASE_AI)

# The label under the rocket is UI text, so it goes through translations.py
LABEL_KEYS = {PHASE_STT: "popup_phase_stt", PHASE_AI: "popup_phase_ai"}

# One accent per phase, shared by the icon and the label: the rocket's window
# blue for the local model, the flame's gold for the AI - both colours are
# already on the screen, so the row belongs to the picture instead of
# shouting over it.
ACCENT_RGB = {PHASE_STT: (100, 180, 255), PHASE_AI: (255, 196, 77)}

# The jokes are English on purpose, like they always were: they are the
# popup's voice, not a setting. Each pool is about its own phase, so the joke
# itself says what is happening even before the label is read.
MESSAGES = {
    PHASE_STT: [
        "Transcribing your thoughts...",
        "Converting speech to text...",
        "Crunching the soundwaves...",
        "Decoding your genius...",
        "Whisper is thinking...",
        "Making your cocktail...",
        "Brewing some magic...",
        "Summoning the words...",
        "Hold my coffee...",
        "Hearing you out, literally...",
        "Turning air into letters...",
        "Local GPU doing push-ups...",
        "Untangling your syllables...",
        "No cloud was harmed so far...",
        "Interpreting your wisdom...",
        "Patience, young padawan...",
        "Shazam! Almost ready...",
        "BRB, transcribing...",
    ],
    PHASE_AI: [
        "Polishing your prose...",
        "Teaching commas some manners...",
        "Evicting the umms and errs...",
        "Proofreading at warp speed...",
        "Sanding the rough edges...",
        "Your swearing stays, promise...",
        "Punctuating, tastefully...",
        "Ironing out the sentences...",
        "Making it sound like you...",
        "Spell-checking the universe...",
        "Reading, not replying...",
        "Capital letters, assemble!...",
        "Trimming the filler words...",
        "Fixing what Whisper misheard...",
        "Almost worth framing...",
    ],
}

# The popup is 350 px wide and the joke sits centred at 10 pt italic; longer
# lines would run into the rounded corners. tests/test_popup_phase.py holds
# every message to this.
MAX_MESSAGE_CHARS = 32


def normalize(phase) -> str:
    """A known phase, or the local one for anything else"""
    return phase if phase in PHASES else PHASE_STT


def pick_message(phase, previous=None) -> str:
    """A random joke for the phase, not the one already on screen"""
    pool = MESSAGES[normalize(phase)]
    choices = [m for m in pool if m != previous] or pool
    return random.choice(choices)


# --- The icon for the GTK overlay, drawn on a cairo context -------------------
#
# The Qt popup draws the same two glyphs with QPainter (popup_window.py). This
# one lives here rather than in wayland_overlay.py so it can be exercised on a
# bare cairo surface in tests, on a machine without a layer shell.

ICON_WIDTH, ICON_HEIGHT = 16, 14
_CAIRO_LINE_CAP_ROUND = 1  # cairo.LINE_CAP_ROUND, without importing cairo here


def _quad_to(cr, x0, y0, qx, qy, x1, y1):
    """Quadratic curve on a cairo context (cairo only has cubics)"""
    cr.curve_to(x0 + 2 / 3 * (qx - x0), y0 + 2 / 3 * (qy - y0),
                x1 + 2 / 3 * (qx - x1), y1 + 2 / 3 * (qy - y1), x1, y1)


def sparkle_path_cairo(cr, cx, cy, r):
    """Four-point sparkle: the tips are r away, the waist pinched to 0.28 r"""
    k = r * 0.28
    cr.move_to(cx, cy - r)
    _quad_to(cr, cx, cy - r, cx + k, cy - k, cx + r, cy)
    _quad_to(cr, cx + r, cy, cx + k, cy + k, cx, cy + r)
    _quad_to(cr, cx, cy + r, cx - k, cy + k, cx - r, cy)
    _quad_to(cr, cx - r, cy, cx - k, cy - k, cx, cy - r)
    cr.close_path()


def draw_icon_cairo(cr, phase, frame: int):
    """
    The phase glyph on a 16x14 canvas: five breathing sound bars for the local
    model, a twinkling four-point sparkle with a small companion for the AI.
    `frame` runs 0..59 with the rocket animation.
    """
    import math
    phase = normalize(phase)
    r, g, b = (c / 255.0 for c in ACCENT_RGB[phase])
    cy = ICON_HEIGHT / 2
    angle = (frame / 60.0) * 2 * math.pi

    if phase == PHASE_STT:
        cr.set_source_rgba(r, g, b, 0.9)
        cr.set_line_width(2)
        cr.set_line_cap(_CAIRO_LINE_CAP_ROUND)
        for i, height in enumerate((4, 8, 11, 7, 5)):
            pulse = 0.75 + 0.25 * math.sin(angle + i * 1.1)
            half = height * pulse / 2
            bx = 2 + i * 3
            cr.move_to(bx, cy - half)
            cr.line_to(bx, cy + half)
            cr.stroke()
        return

    twinkle = 0.8 + 0.2 * math.sin(angle)
    cr.set_source_rgba(r, g, b, twinkle)
    sparkle_path_cairo(cr, 6, cy, 6 * twinkle)
    cr.fill()
    cr.set_source_rgba(r, g, b, 0.85 * (1.2 - twinkle))
    sparkle_path_cairo(cr, 13, cy - 4.5, 2.5)
    cr.fill()
