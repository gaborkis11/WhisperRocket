#!/usr/bin/env python3
"""
WhisperRocket - Wayland Overlay (GTK Layer-Shell)
Fókusz-mentes popup Wayland-hez a wlr-layer-shell protokoll használatával.
Design: Qt verzió alapján - szimmetrikus waveform, rakéta animáció
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('GtkLayerShell', '0.1')
gi.require_version('Pango', '1.0')
from gi.repository import Gtk, GtkLayerShell, GLib, Gdk, Pango
import cairo
import math
import random
import threading
from queue import Queue, Empty
from enum import Enum, auto

from translations import t


def init_gtk():
    """GTK inicializálása - FŐSZÁLBÓL hívandó!"""
    Gtk.init()


def pump_gtk_events():
    """
    GTK event-ek feldolgozása - Qt timer-ből hívandó.
    Ez lehetővé teszi, hogy a GTK ablak működjön a Qt event loop mellett.
    """
    context = GLib.MainContext.default()
    while context.pending():
        context.iteration(False)


class OverlayState(Enum):
    """Overlay állapotok"""
    HIDDEN = auto()
    RECORDING = auto()
    PROCESSING = auto()
    TEXT_PREVIEW = auto()


class WaveformWidget(Gtk.DrawingArea):
    """Szimmetrikus waveform widget - Qt verzió alapján"""

    BAR_COUNT = 45
    BAR_WIDTH = 3
    BAR_GAP = 3
    MAX_HALF_HEIGHT = 28  # Max fél-magasság (fel ÉS le)

    def __init__(self):
        super().__init__()
        self.amplitude = 0.0
        self.smoothed_amplitude = 0.0
        self.smoothing_factor = 0.15

        # Gauss súlyok (közép = 1.0, szélek = ~0.3)
        center = self.BAR_COUNT // 2
        sigma = self.BAR_COUNT / 4
        self.bar_weights = []
        for i in range(self.BAR_COUNT):
            distance = abs(i - center)
            weight = math.exp(-(distance ** 2) / (2 * sigma ** 2))
            self.bar_weights.append(weight)

        total_width = self.BAR_COUNT * (self.BAR_WIDTH + self.BAR_GAP)
        self.set_size_request(total_width, self.MAX_HALF_HEIGHT * 2 + 4)

        self.connect("draw", self._on_draw)

    def _on_draw(self, widget, cr):
        """Cairo rajzolás - szimmetrikus sávok"""
        width = self.get_allocated_width()
        height = self.get_allocated_height()
        center_y = height // 2

        total_bar_width = self.BAR_COUNT * (self.BAR_WIDTH + self.BAR_GAP)
        start_x = (width - total_bar_width) // 2

        # Simított amplitude normalizálás
        normalized_amp = min(self.smoothed_amplitude * 35, 1.0)

        for i in range(self.BAR_COUNT):
            # Gauss súlyozás + enyhe véletlenszerűség
            weight = self.bar_weights[i]
            random_factor = random.uniform(0.9, 1.1)

            # Fél-magasság számítás (min 2px)
            half_height = max(2, int(normalized_amp * self.MAX_HALF_HEIGHT * weight * random_factor))

            x = start_x + i * (self.BAR_WIDTH + self.BAR_GAP)

            # Fehér szín
            cr.set_source_rgba(1, 1, 1, 0.95)

            # Felső fél - lekerekített
            self._draw_rounded_rect(cr, x, center_y - half_height, self.BAR_WIDTH, half_height, 1.5)
            cr.fill()

            # Alsó fél - lekerekített (tükrözve)
            self._draw_rounded_rect(cr, x, center_y, self.BAR_WIDTH, half_height, 1.5)
            cr.fill()

        return False

    def _draw_rounded_rect(self, cr, x, y, width, height, radius):
        """Lekerekített téglalap"""
        if height < radius * 2:
            radius = height / 2
        if radius < 0.5:
            cr.rectangle(x, y, width, height)
            return

        cr.move_to(x + radius, y)
        cr.line_to(x + width - radius, y)
        cr.arc(x + width - radius, y + radius, radius, -math.pi/2, 0)
        cr.line_to(x + width, y + height - radius)
        cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi/2)
        cr.line_to(x + radius, y + height)
        cr.arc(x + radius, y + height - radius, radius, math.pi/2, math.pi)
        cr.line_to(x, y + radius)
        cr.arc(x + radius, y + radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()

    def set_amplitude(self, amplitude: float):
        """Amplitúdó beállítása exponenciális simítással"""
        self.amplitude = amplitude
        self.smoothed_amplitude = (
            self.smoothed_amplitude * (1 - self.smoothing_factor) +
            self.amplitude * self.smoothing_factor
        )
        self.queue_draw()


class RocketWidget(Gtk.DrawingArea):
    """Rakéta animáció widget - Qt verzió alapján"""

    def __init__(self):
        super().__init__()
        self.animation_frame = 0
        self.stars = []
        self._init_stars()

        self.set_size_request(350, 60)
        self.connect("draw", self._on_draw)

    def _init_stars(self):
        """Csillagok inicializálása"""
        self.stars = []
        for _ in range(15):
            x = random.randint(0, 350)
            y = random.randint(5, 55)
            size = random.uniform(1.5, 3.5)
            speed = random.uniform(2, 5)
            self.stars.append([x, y, size, speed])

    def _update_stars(self):
        """Csillagok mozgatása balra"""
        for star in self.stars:
            star[0] -= star[3]
            if star[0] < -5:
                star[0] = 355
                star[1] = random.randint(5, 55)
                star[2] = random.uniform(1.5, 3.5)
                star[3] = random.uniform(2, 5)

    def _on_draw(self, widget, cr):
        """Cairo rajzolás - csillagok + rakéta"""
        self._update_stars()

        # Csillagok rajzolása
        for star in self.stars:
            x, y, size, speed = star
            brightness = min(1.0, 0.4 + speed * 0.12)
            cr.set_source_rgba(brightness, brightness, brightness, 0.8)
            cr.arc(x, y, size, 0, 2 * math.pi)
            cr.fill()

        # Rakéta középen
        self._draw_rocket(cr, 190, 30)

        self.animation_frame = (self.animation_frame + 1) % 60
        return False

    def _draw_rocket(self, cr, x, y):
        """Rakéta rajzolása - Qt verzió alapján"""
        scale = 0.7

        # Lángok (animált)
        flame_offset = self.animation_frame % 10
        flame_length = 18 + flame_offset + random.randint(-3, 3)

        # Külső láng (narancssárga)
        cr.set_source_rgba(1.0, 0.55, 0, 0.8)
        cr.move_to(x - 20 * scale, y)
        cr.curve_to(
            x - (20 + flame_length) * scale, y - 8 * scale,
            x - (20 + flame_length) * scale, y + 8 * scale,
            x - 20 * scale, y
        )
        cr.fill()

        # Belső láng (sárga)
        inner_len = flame_length * 0.6
        cr.set_source_rgba(1.0, 1.0, 0.4, 0.9)
        cr.move_to(x - 20 * scale, y)
        cr.curve_to(
            x - (20 + inner_len) * scale, y - 4 * scale,
            x - (20 + inner_len) * scale, y + 4 * scale,
            x - 20 * scale, y
        )
        cr.fill()

        # Rakéta test (világosszürke)
        cr.set_source_rgb(0.92, 0.92, 0.94)
        cr.move_to(x + 30 * scale, y)
        cr.curve_to(x + 25 * scale, y - 12 * scale, x - 5 * scale, y - 12 * scale, x - 5 * scale, y - 12 * scale)
        cr.line_to(x - 20 * scale, y - 8 * scale)
        cr.line_to(x - 20 * scale, y + 8 * scale)
        cr.line_to(x - 5 * scale, y + 12 * scale)
        cr.curve_to(x - 5 * scale, y + 12 * scale, x + 25 * scale, y + 12 * scale, x + 30 * scale, y)
        cr.fill()

        # Orrkúp (piros)
        cr.set_source_rgb(0.94, 0.35, 0.35)
        cr.move_to(x + 30 * scale, y)
        cr.curve_to(x + 28 * scale, y - 8 * scale, x + 15 * scale, y - 10 * scale, x + 15 * scale, y - 10 * scale)
        cr.line_to(x + 15 * scale, y + 10 * scale)
        cr.curve_to(x + 15 * scale, y + 10 * scale, x + 28 * scale, y + 8 * scale, x + 30 * scale, y)
        cr.fill()

        # Felső szárny (piros)
        cr.move_to(x - 10 * scale, y - 10 * scale)
        cr.line_to(x - 20 * scale, y - 22 * scale)
        cr.line_to(x - 22 * scale, y - 10 * scale)
        cr.close_path()
        cr.fill()

        # Alsó szárny (piros)
        cr.move_to(x - 10 * scale, y + 10 * scale)
        cr.line_to(x - 20 * scale, y + 22 * scale)
        cr.line_to(x - 22 * scale, y + 10 * scale)
        cr.close_path()
        cr.fill()

        # Ablak (kék kör)
        cr.set_source_rgb(0.39, 0.71, 1.0)
        cr.arc(x + 5 * scale, y, 6 * scale, 0, 2 * math.pi)
        cr.fill()

        # Ablak fény
        cr.set_source_rgb(0.78, 0.9, 1.0)
        cr.arc(x + 3 * scale, y - 2 * scale, 2 * scale, 0, 2 * math.pi)
        cr.fill()

    def animate(self):
        """Animáció frissítése"""
        self.queue_draw()


class WaylandOverlay:
    """
    GTK Layer-Shell alapú overlay Wayland-hez.
    NEM lop fókuszt a keyboard_interactivity=NONE beállítás miatt.
    """

    PROCESSING_MESSAGES = [
        "Transcribing your thoughts...",
        "Converting speech to text...",
        "Processing your words...",
        "Making your cocktail...",
        "Brewing some magic...",
        "Decoding your genius...",
        "Hold my coffee...",
        "Crunching the soundwaves...",
        "Whisper is thinking...",
        "Almost got it...",
        "Loading awesomeness...",
        "Patience, young padawan...",
        "BRB, transcribing...",
    ]

    def __init__(self, amplitude_queue: Queue, hotkey: str = "Ctrl+Shift+S",
                 popup_duration: int = 5, ui_language: str = "en"):
        self.amplitude_queue = amplitude_queue
        self.hotkey = hotkey
        self.popup_duration = popup_duration
        self.ui_lang = ui_language

        self.state = OverlayState.HIDDEN
        self.transcribed_text = ""
        self.countdown_remaining = 0
        self.current_message = ""

        # Timer ID-k
        self._animation_timer_id = None
        self._countdown_timer_id = None
        self._message_timer_id = None
        self._auto_hide_timer_id = None

        # GTK inicializálás - AZONNAL, nem lazy
        self._window = None
        self._waveform = None
        self._rocket = None
        self._initialized = False

        # Ablak előre létrehozása ÉS "bemelegítése"
        self._ensure_initialized()
        # Warmup: megjelenítjük, pumpálunk, elrejtjük
        self._window.show_all()
        # Manuális GTK event feldolgozás (mert a Qt timer még nem fut!)
        for _ in range(50):  # Több iteráció a biztonság kedvéért
            pump_gtk_events()
        self._window.hide()
        for _ in range(10):
            pump_gtk_events()

    def _ensure_initialized(self):
        """GTK ablak inicializálása"""
        if self._initialized:
            return

        # Ablak létrehozása
        self._window = Gtk.Window()
        self._window.set_default_size(350, 100)
        self._window.set_app_paintable(True)

        # Átlátszó háttér
        screen = self._window.get_screen()
        visual = screen.get_rgba_visual()
        if visual:
            self._window.set_visual(visual)

        # Layer shell inicializálás
        GtkLayerShell.init_for_window(self._window)
        GtkLayerShell.set_layer(self._window, GtkLayerShell.Layer.TOP)
        GtkLayerShell.set_keyboard_mode(self._window, GtkLayerShell.KeyboardMode.NONE)
        GtkLayerShell.set_anchor(self._window, GtkLayerShell.Edge.BOTTOM, True)
        GtkLayerShell.set_margin(self._window, GtkLayerShell.Edge.BOTTOM, 80)
        GtkLayerShell.set_exclusive_zone(self._window, 0)

        # Fő konténer - custom draw-val a háttérhez
        self._overlay_box = Gtk.Overlay()
        self._window.add(self._overlay_box)

        # Háttér rajzoló
        self._bg_area = Gtk.DrawingArea()
        self._bg_area.connect("draw", self._draw_background)
        self._overlay_box.add(self._bg_area)

        # Content box
        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._main_box.set_margin_top(8)
        self._main_box.set_margin_bottom(8)
        self._main_box.set_margin_start(15)
        self._main_box.set_margin_end(15)
        self._overlay_box.add_overlay(self._main_box)

        # Waveform widget
        self._waveform = WaveformWidget()
        self._waveform.set_halign(Gtk.Align.CENTER)
        self._waveform.set_valign(Gtk.Align.CENTER)
        self._main_box.pack_start(self._waveform, True, True, 0)

        # Rocket widget (kezdetben rejtett)
        self._rocket = RocketWidget()
        self._rocket.set_halign(Gtk.Align.CENTER)
        self._rocket.set_valign(Gtk.Align.CENTER)
        self._rocket.set_no_show_all(True)
        self._main_box.pack_start(self._rocket, True, True, 0)

        # Alsó sor - labelek
        self._bottom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self._bottom_box.set_margin_top(4)
        self._main_box.pack_start(self._bottom_box, False, False, 0)

        # Bal oldal: piros kör + Recording
        self._left_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._bottom_box.pack_start(self._left_box, False, False, 0)

        self._rec_dot = Gtk.DrawingArea()
        self._rec_dot.set_size_request(10, 10)
        self._rec_dot.connect("draw", self._draw_rec_dot)
        self._left_box.pack_start(self._rec_dot, False, False, 0)

        self._status_label = Gtk.Label()
        self._status_label.set_markup(f'<span foreground="#a0a0a0" font_size="small">{t("popup_recording", self.ui_lang)}</span>')
        self._left_box.pack_start(self._status_label, False, False, 0)

        # Jobb oldal: hotkey gombok
        self._right_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._bottom_box.pack_end(self._right_box, False, False, 0)

        hotkey_display = self.hotkey.replace("+", "+").title()

        # Finish label + gomb
        self._finish_label = Gtk.Label()
        self._finish_label.set_markup(f'<span foreground="#787878" font_size="small">{t("popup_finish", self.ui_lang)}</span>')
        self._right_box.pack_start(self._finish_label, False, False, 0)

        self._finish_btn = Gtk.Label()
        self._finish_btn.set_markup(f'<span foreground="#b4b4b4" font_size="small" background="#505050"> {hotkey_display} </span>')
        self._right_box.pack_start(self._finish_btn, False, False, 0)

        # Cancel label + gomb
        self._cancel_label = Gtk.Label()
        self._cancel_label.set_markup(f'<span foreground="#787878" font_size="small">{t("popup_cancel", self.ui_lang)}</span>')
        self._right_box.pack_start(self._cancel_label, False, False, 0)

        self._cancel_btn = Gtk.Label()
        self._cancel_btn.set_markup('<span foreground="#b4b4b4" font_size="small" background="#505050"> Esc </span>')
        self._right_box.pack_start(self._cancel_btn, False, False, 0)

        # Processing message label (kezdetben rejtett)
        self._message_label = Gtk.Label()
        self._message_label.set_no_show_all(True)
        self._message_label.set_halign(Gtk.Align.CENTER)
        self._main_box.pack_start(self._message_label, False, False, 0)

        # Text preview label (kezdetben rejtett)
        self._text_label = Gtk.Label()
        self._text_label.set_no_show_all(True)
        self._text_label.set_line_wrap(True)
        self._text_label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self._text_label.set_max_width_chars(45)
        self._text_label.set_halign(Gtk.Align.CENTER)
        self._main_box.pack_start(self._text_label, False, False, 0)

        # Countdown label (kezdetben rejtett)
        self._countdown_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self._countdown_box.set_no_show_all(True)
        self._countdown_box.set_halign(Gtk.Align.CENTER)
        self._main_box.pack_start(self._countdown_box, False, False, 0)

        self._copied_label = Gtk.Label()
        self._copied_label.set_markup('<span foreground="#6b7280" font_size="small">Copied to clipboard</span>')
        self._countdown_box.pack_start(self._copied_label, False, False, 0)

        self._countdown_label = Gtk.Label()
        self._countdown_box.pack_start(self._countdown_label, False, False, 0)

        self._initialized = True

    def _draw_background(self, widget, cr):
        """Háttér rajzolása - lekerekített téglalap"""
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()

        # Lekerekített téglalap
        radius = 12
        cr.move_to(radius, 0)
        cr.line_to(width - radius, 0)
        cr.arc(width - radius, radius, radius, -math.pi/2, 0)
        cr.line_to(width, height - radius)
        cr.arc(width - radius, height - radius, radius, 0, math.pi/2)
        cr.line_to(radius, height)
        cr.arc(radius, height - radius, radius, math.pi/2, math.pi)
        cr.line_to(0, radius)
        cr.arc(radius, radius, radius, math.pi, 3*math.pi/2)
        cr.close_path()

        # Sötét háttér kis átlátszósággal
        cr.set_source_rgba(0.102, 0.102, 0.102, 0.94)  # #1a1a1a
        cr.fill()

        return False

    def _draw_rec_dot(self, widget, cr):
        """Piros felvétel pont rajzolása"""
        cr.set_source_rgb(0.937, 0.267, 0.267)  # #ef4444
        cr.arc(5, 5, 5, 0, 2 * math.pi)
        cr.fill()
        return False

    def _run_on_gtk_thread(self, func):
        """Függvény futtatása - már a főszálban vagyunk, közvetlen hívás"""
        func()

    # === Signal-szerű interface ===

    class _SignalEmitter:
        def __init__(self):
            self._callback = None

        def connect(self, callback):
            self._callback = callback

        def emit(self, *args):
            if self._callback:
                self._callback(*args)

    @property
    def request_show_popup(self):
        if not hasattr(self, '_request_show_popup'):
            self._request_show_popup = self._SignalEmitter()
            self._request_show_popup._callback = lambda: self._run_on_gtk_thread(self.show_recording)
        return self._request_show_popup

    @property
    def request_show_processing(self):
        if not hasattr(self, '_request_show_processing'):
            self._request_show_processing = self._SignalEmitter()
            self._request_show_processing._callback = lambda: self._run_on_gtk_thread(self.show_processing)
        return self._request_show_processing

    @property
    def request_show_text(self):
        if not hasattr(self, '_request_show_text'):
            self._request_show_text = self._SignalEmitter()
            self._request_show_text._callback = lambda text: self._run_on_gtk_thread(lambda: self.show_text(text))
        return self._request_show_text

    @property
    def request_hide_popup(self):
        if not hasattr(self, '_request_hide_popup'):
            self._request_hide_popup = self._SignalEmitter()
            self._request_hide_popup._callback = lambda: self._run_on_gtk_thread(self.hide)
        return self._request_hide_popup

    # === Állapot váltások ===

    def show_recording(self):
        """Recording állapot"""
        self._ensure_initialized()
        self._stop_all_timers()

        self.state = OverlayState.RECORDING

        # Widgetek láthatósága
        self._waveform.show()
        self._rocket.hide()
        self._bottom_box.show()
        self._message_label.hide()
        self._text_label.hide()
        self._countdown_box.hide()

        # Status label
        self._status_label.set_markup(f'<span foreground="#a0a0a0" font_size="small">{t("popup_recording", self.ui_lang)}</span>')

        # Piros dot
        self._rec_dot.queue_draw()

        # Méret
        self._window.set_default_size(350, 100)

        # Animáció (60 FPS)
        self._animation_timer_id = GLib.timeout_add(16, self._animate_recording)

        self._window.show_all()
        self._rocket.hide()
        self._message_label.hide()
        self._text_label.hide()
        self._countdown_box.hide()

    def _animate_recording(self):
        """Recording animáció"""
        if self.state != OverlayState.RECORDING:
            return False

        # Amplitúdó olvasása
        amplitude = 0.0
        try:
            while True:
                amplitude = self.amplitude_queue.get_nowait()
        except Empty:
            pass

        self._waveform.set_amplitude(amplitude)
        return True

    def show_processing(self):
        """Processing állapot - rakéta animáció"""
        self._ensure_initialized()
        self._stop_all_timers()

        self.state = OverlayState.PROCESSING
        self.current_message = random.choice(self.PROCESSING_MESSAGES)

        # Widgetek láthatósága
        self._waveform.hide()
        self._rocket.show()
        self._bottom_box.hide()
        self._message_label.show()
        self._text_label.hide()
        self._countdown_box.hide()

        # Message label
        self._message_label.set_markup(f'<span foreground="#c8c8c8" font_style="italic">{self.current_message}</span>')

        # Méret
        self._window.set_default_size(350, 100)

        # Animáció
        self._animation_timer_id = GLib.timeout_add(16, self._animate_processing)

        # Üzenet váltás
        self._message_timer_id = GLib.timeout_add(2000, self._next_message)

        self._window.show_all()
        self._waveform.hide()
        self._bottom_box.hide()
        self._text_label.hide()
        self._countdown_box.hide()

    def _animate_processing(self):
        """Processing animáció"""
        if self.state != OverlayState.PROCESSING:
            return False
        self._rocket.animate()
        return True

    def _next_message(self):
        """Következő vicces üzenet"""
        if self.state != OverlayState.PROCESSING:
            return False
        self.current_message = random.choice(self.PROCESSING_MESSAGES)
        self._message_label.set_markup(f'<span foreground="#c8c8c8" font_style="italic">{self.current_message}</span>')
        return True

    def show_text(self, text: str):
        """Szöveg megjelenítése"""
        self._ensure_initialized()
        self._stop_all_timers()

        self.state = OverlayState.TEXT_PREVIEW
        self.transcribed_text = text
        self.countdown_remaining = self.popup_duration

        # Widgetek láthatósága
        self._waveform.hide()
        self._rocket.hide()
        self._bottom_box.hide()
        self._message_label.hide()
        self._text_label.show()
        self._countdown_box.show()

        # Szöveg (max 80 karakter)
        display_text = text
        if len(display_text) > 80:
            display_text = display_text[:77] + "..."

        # Escape markup karakterek
        display_text = display_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        self._text_label.set_markup(
            f'<span foreground="#22c55e" font_size="large">✓</span>  '
            f'<span foreground="#ffffff">"{display_text}"</span>'
        )

        # Countdown
        self._countdown_label.set_markup(f'<span foreground="#fbbf24" weight="bold">{self.countdown_remaining}s</span>')

        # Méret
        self._window.set_default_size(350, 100)

        # Countdown timer
        self._countdown_timer_id = GLib.timeout_add(1000, self._update_countdown)

        # Auto-hide
        self._auto_hide_timer_id = GLib.timeout_add(self.popup_duration * 1000, self._auto_hide)

        self._window.show_all()
        self._waveform.hide()
        self._rocket.hide()
        self._bottom_box.hide()
        self._message_label.hide()

    def _update_countdown(self):
        """Visszaszámláló frissítése"""
        if self.state != OverlayState.TEXT_PREVIEW:
            return False

        self.countdown_remaining -= 1
        if self.countdown_remaining >= 0:
            self._countdown_label.set_markup(f'<span foreground="#fbbf24" weight="bold">{self.countdown_remaining}s</span>')
            return True
        return False

    def _auto_hide(self):
        """Automatikus elrejtés"""
        if self.state == OverlayState.TEXT_PREVIEW:
            self.hide()
        return False

    def hide(self):
        """Overlay elrejtése"""
        self._stop_all_timers()
        self.state = OverlayState.HIDDEN

        if self._window:
            self._window.hide()

    def _stop_all_timers(self):
        """Összes timer leállítása"""
        if self._animation_timer_id:
            GLib.source_remove(self._animation_timer_id)
            self._animation_timer_id = None
        if self._countdown_timer_id:
            GLib.source_remove(self._countdown_timer_id)
            self._countdown_timer_id = None
        if self._message_timer_id:
            GLib.source_remove(self._message_timer_id)
            self._message_timer_id = None
        if self._auto_hide_timer_id:
            GLib.source_remove(self._auto_hide_timer_id)
            self._auto_hide_timer_id = None


# Tesztelés (főszálas GTK)
if __name__ == "__main__":
    from queue import Queue
    import time

    # GTK inicializálása FŐSZÁLBAN
    init_gtk()

    # Amplitude queue és overlay
    amp_queue = Queue()
    overlay = WaylandOverlay(amp_queue, "Alt+S", 5, "en")

    # Teszt: recording megjelenítése
    print("Showing recording...")
    overlay.request_show_popup.emit()

    # Szimulált audio háttérszálban
    def simulate_audio():
        import math
        t = 0
        while True:
            amp = abs(math.sin(t * 3)) * 0.5 + random.random() * 0.2
            amp_queue.put(amp)
            t += 0.05
            time.sleep(0.05)

    audio_thread = threading.Thread(target=simulate_audio, daemon=True)
    audio_thread.start()

    # GTK main loop futtatása (főszál)
    # Ez blokkoló - 4 másodperc után processing
    def switch_to_processing():
        print("Showing processing...")
        overlay.request_show_processing.emit()
        return False

    def switch_to_text():
        print("Showing text...")
        overlay.request_show_text.emit("This is a test transcription!")
        return False

    def quit_app():
        print("Done!")
        Gtk.main_quit()
        return False

    GLib.timeout_add(4000, switch_to_processing)
    GLib.timeout_add(8000, switch_to_text)
    GLib.timeout_add(14000, quit_app)

    Gtk.main()
