#!/usr/bin/env python3
"""
WhisperWarp - Recording Popup Window
Valós idejű waveform vizualizáció felvétel közben
Transzkripció utáni szöveg megjelenítés
"""
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF, Slot, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from queue import Queue, Empty
from enum import Enum, auto
from translations import t
import sys
import math
import random
import pyperclip


class PopupState(Enum):
    """Popup állapotok"""
    HIDDEN = auto()
    RECORDING = auto()
    PROCESSING = auto()  # Feldolgozás közben
    TEXT_PREVIEW = auto()
    TEXT_EXPANDED = auto()


class RecordingPopup(QWidget):
    """Frameless popup ablak waveform vizualizációval"""

    # Signalok thread-safe kommunikációhoz
    request_show_popup = Signal()
    request_show_processing = Signal()
    request_show_text = Signal(str)
    request_hide_popup = Signal()

    def __init__(self, amplitude_queue: Queue, hotkey: str = "Alt+S", popup_duration: int = 5, ui_language: str = "en"):
        super().__init__()
        self.amplitude_queue = amplitude_queue
        self.hotkey = hotkey  # Beállított hotkey megjelenítéshez
        self.popup_duration = popup_duration  # Popup megjelenítési idő (másodperc)
        self.ui_lang = ui_language  # UI nyelv
        self.current_amplitude = 0.0  # Aktuális hangerő (nyers)
        self.smoothed_amplitude = 0.0  # Simított hangerő (megjelenítéshez)
        self.bar_count = 45  # Oszlopok száma
        self.drag_position = None
        self.saved_position = None  # Session alatti pozíció memória

        # Állapotgép
        self.state = PopupState.HIDDEN
        self.transcribed_text = ""  # Leiratott szöveg

        # Auto-hide timer
        self.auto_hide_timer = QTimer()
        self.auto_hide_timer.setSingleShot(True)
        self.auto_hide_timer.timeout.connect(self._auto_hide)
        self.auto_hide_seconds = popup_duration  # Konfigurálható időtartam

        # Visszaszámláló timer (másodpercenként frissít)
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_remaining = 0  # Hátralévő másodpercek

        # Méretek
        self.base_width = 350
        self.base_height = 100  # Nagyobb, hogy az equalizer ne lógjon bele
        self.preview_height = 140  # Fejléc + szöveg előnézet
        self.expanded_height = 220  # Fejléc + teljes szöveg + Copy

        # Gomb területek (expandált nézethez)
        self.close_btn_rect = QRectF(0, 0, 0, 0)
        self.copy_btn_rect = QRectF(0, 0, 0, 0)

        # Processing állapot - vicces üzenetek
        self.processing_messages = [
            # Klasszikus
            "Transcribing your thoughts...",
            "Converting speech to text...",
            "Processing your words...",
            "Almost there...",
            "Just a moment...",
            # Vicces / Funny
            "Making your cocktail...",
            "Brewing some magic...",
            "Cooking up your text...",
            "Summoning the words...",
            "Decoding your genius...",
            "Translating brilliance...",
            "Working overtime here...",
            "Hold my coffee...",
            "Doing the heavy lifting...",
            "Crunching the soundwaves...",
            "Teaching AI to listen...",
            "One moment of magic...",
            "Converting genius to text...",
            "Whisper is thinking...",
            "Interpreting your wisdom...",
            "Almost got it...",
            "Patience, young padawan...",
            "Loading awesomeness...",
            "Shazam! Almost ready...",
            "BRB, transcribing...",
        ]
        self.current_message = random.choice(self.processing_messages)
        self.animation_frame = 0

        # Üzenet váltó timer (2 másodpercenként)
        self.message_timer = QTimer()
        self.message_timer.timeout.connect(self._next_message)

        # Rakéta animáció - csillagok/részecskék
        self.stars = []  # [(x, y, size, speed), ...]
        self._init_stars()

        # Simítási faktor (0.0-1.0, alacsonyabb = lágyabb)
        self.smoothing_factor = 0.15  # Lassú, lágy követés

        # Gauss súlyok előre kiszámítva (közép = 1.0, szélek = ~0.3)
        center = self.bar_count // 2
        sigma = self.bar_count / 4  # Szélesség
        self.bar_weights = []
        for i in range(self.bar_count):
            distance = abs(i - center)
            weight = math.exp(-(distance ** 2) / (2 * sigma ** 2))
            self.bar_weights.append(weight)

        # Ablak beállítások - NE vegyen fókuszt!
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |  # Nem jelenik meg a taskbar-on
            Qt.WindowType.WindowDoesNotAcceptFocus  # Nem vesz fókuszt!
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)  # Megjelenéskor se aktiválódjon

        # Méret
        self.setFixedSize(350, 80)

        # Középre pozícionálás
        self._center_on_screen()

        # Signal-slot összekötések (thread-safe)
        self.request_show_popup.connect(self.show_popup)
        self.request_show_processing.connect(self.show_processing)
        self.request_show_text.connect(self.show_text)
        self.request_hide_popup.connect(self.hide_popup)

        # Timer a waveform frissítéséhez (60 FPS)
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_waveform)
        self.update_timer.start(16)  # ~60 FPS

    def _center_on_screen(self):
        """Ablak középre helyezése"""
        if self.saved_position:
            self.move(self.saved_position)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.availableGeometry()
                x = (geometry.width() - self.width()) // 2
                y = (geometry.height() - self.height()) // 2
                self.move(x, y)

    @Slot()
    def _update_waveform(self):
        """Waveform adatok frissítése a queue-ból"""
        try:
            # Csak a legutolsó amplitude értéket használjuk
            while True:
                self.current_amplitude = self.amplitude_queue.get_nowait()
        except Empty:
            pass

        # Exponenciális simítás - lágy, fokozatos követés
        self.smoothed_amplitude = (
            self.smoothed_amplitude * (1 - self.smoothing_factor) +
            self.current_amplitude * self.smoothing_factor
        )

        # UI frissítés
        self.update()

    def paintEvent(self, event):
        """Ablak rajzolása állapot alapján"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Háttér - sötét lekerekített téglalap
        bg_color = QColor(26, 26, 26, 240)  # #1a1a1a, kis átlátszóság
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        painter.fillPath(path, QBrush(bg_color))

        # DEBUG: állapot kiírás (csak néha, hogy ne spammeljen)
        import time
        if not hasattr(self, '_last_state_log') or time.time() - self._last_state_log > 1:
            print(f"[DEBUG paintEvent] state={self.state}")
            self._last_state_log = time.time()

        # Állapot alapú rajzolás
        if self.state == PopupState.RECORDING:
            self._draw_waveform(painter)
            self._draw_recording_label(painter)
        elif self.state == PopupState.PROCESSING:
            self._draw_processing(painter)
        elif self.state == PopupState.TEXT_PREVIEW:
            self._draw_text_preview(painter)
        elif self.state == PopupState.TEXT_EXPANDED:
            self._draw_text_expanded(painter)

    def _draw_waveform(self, painter: QPainter):
        """Equalizer stílusú waveform - statikus, szimmetrikus oszlopok"""
        bar_width = 3
        bar_gap = 3
        total_width = self.bar_count * (bar_width + bar_gap)

        # Középre igazítás - feljebb, hogy ne lógjon az alsó részbe
        start_x = (self.width() - total_width) // 2
        center_y = 40  # Fix pozíció fent
        max_half_height = 25  # Max fél-magasság (fel ÉS le is ennyi)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))  # Fehér oszlopok

        # Simított amplitude normalizálás
        normalized_amp = min(self.smoothed_amplitude * 35, 1.0)

        for i in range(self.bar_count):
            # Gauss súlyozás + enyhe véletlenszerűség (kevésbé agresszív)
            weight = self.bar_weights[i]
            random_factor = random.uniform(0.9, 1.1)  # Kisebb variáció

            # Fél-magasság számítás (min 2px)
            half_height = max(2, int(normalized_amp * max_half_height * weight * random_factor))

            x = start_x + i * (bar_width + bar_gap)

            # Szimmetrikus rajzolás - középvonaltól FEL és LE
            # Felső fél
            bar_path_top = QPainterPath()
            bar_path_top.addRoundedRect(
                QRectF(x, center_y - half_height, bar_width, half_height),
                1.5, 1.5
            )
            painter.fillPath(bar_path_top, QBrush(QColor(255, 255, 255)))

            # Alsó fél (tükrözve)
            bar_path_bottom = QPainterPath()
            bar_path_bottom.addRoundedRect(
                QRectF(x, center_y, bar_width, half_height),
                1.5, 1.5
            )
            painter.fillPath(bar_path_bottom, QBrush(QColor(255, 255, 255)))

    def _draw_recording_label(self, painter: QPainter):
        """Recording felirat, piros kör, és hotkey gombok"""
        padding = 15

        # Piros kör + Recording (bal oldalon)
        circle_x = padding
        circle_y = self.height() - 20
        circle_radius = 5

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(239, 68, 68)))  # Piros
        painter.drawEllipse(QPoint(circle_x, circle_y), circle_radius, circle_radius)

        painter.setPen(QPen(QColor(160, 160, 160)))
        painter.setFont(QFont("Sans", 9))
        painter.drawText(circle_x + 12, circle_y + 4, t("popup_recording", self.ui_lang))

        # Hotkey gombok jobb oldalon: "Finish [Alt+S]" | "Cancel [Esc]"
        btn_y = self.height() - 28
        btn_height = 20

        # Hotkey formázása (alt+s -> Alt+S)
        hotkey_display = self.hotkey.replace("+", "+").title()

        # Cancel gomb (jobb szélső)
        cancel_text = "Esc"
        painter.setFont(QFont("Sans", 8))
        fm = painter.fontMetrics()

        cancel_btn_w = fm.horizontalAdvance(cancel_text) + 12
        cancel_btn_x = self.width() - padding - cancel_btn_w

        # Cancel gomb háttér
        cancel_rect = QRectF(cancel_btn_x, btn_y, cancel_btn_w, btn_height)
        cancel_path = QPainterPath()
        cancel_path.addRoundedRect(cancel_rect, 4, 4)
        painter.fillPath(cancel_path, QBrush(QColor(80, 80, 80, 150)))

        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(int(cancel_btn_x + 6), int(btn_y + 14), cancel_text)

        # "Cancel" label
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.drawText(int(cancel_btn_x - 45), int(btn_y + 14), t("popup_cancel", self.ui_lang))

        # Finish gomb (Cancel előtt)
        finish_text = hotkey_display
        finish_btn_w = fm.horizontalAdvance(finish_text) + 12
        finish_btn_x = cancel_btn_x - 55 - finish_btn_w

        # Finish gomb háttér
        finish_rect = QRectF(finish_btn_x, btn_y, finish_btn_w, btn_height)
        finish_path = QPainterPath()
        finish_path.addRoundedRect(finish_rect, 4, 4)
        painter.fillPath(finish_path, QBrush(QColor(80, 80, 80, 150)))

        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(int(finish_btn_x + 6), int(btn_y + 14), finish_text)

        # "Finish" label
        painter.setPen(QPen(QColor(120, 120, 120)))
        painter.drawText(int(finish_btn_x - 40), int(btn_y + 14), t("popup_finish", self.ui_lang))

    def _init_stars(self):
        """Csillagok inicializálása a háttérhez"""
        self.stars = []
        for _ in range(15):
            x = random.randint(0, self.base_width)
            y = random.randint(10, 55)
            size = random.uniform(1.5, 3.5)
            speed = random.uniform(2, 5)
            self.stars.append([x, y, size, speed])

    def _update_stars(self):
        """Csillagok mozgatása balra (űrrepülés illúzió)"""
        for star in self.stars:
            star[0] -= star[3]  # x -= speed
            # Ha kilép bal oldalon, újra jobb oldalon
            if star[0] < -5:
                star[0] = self.base_width + 5
                star[1] = random.randint(10, 55)
                star[2] = random.uniform(1.5, 3.5)
                star[3] = random.uniform(2, 5)

    def _draw_stars(self, painter: QPainter):
        """Csillagok rajzolása"""
        painter.setPen(Qt.PenStyle.NoPen)
        for star in self.stars:
            x, y, size, speed = star
            # Gyorsabb csillagok fényesebbek
            brightness = int(100 + speed * 30)
            painter.setBrush(QBrush(QColor(brightness, brightness, brightness, 200)))
            painter.drawEllipse(QPoint(int(x), int(y)), int(size), int(size))

    def _draw_rocket(self, painter: QPainter, x: int, y: int):
        """Rakéta rajzolása flat-design stílusban (jobbra néz)"""
        # Méretezés
        scale = 0.7

        # Lángok (animált) - ELŐSZÖR rajzoljuk, hogy a rakéta mögött legyen
        flame_offset = self.animation_frame % 10
        flame_length = 18 + flame_offset + random.randint(-3, 3)

        # Külső láng (narancssárga)
        flame_outer = QPainterPath()
        flame_outer.moveTo(x - 20 * scale, y)
        flame_outer.quadTo(x - (20 + flame_length) * scale, y - 8 * scale,
                          x - (25 + flame_length) * scale, y)
        flame_outer.quadTo(x - (20 + flame_length) * scale, y + 8 * scale,
                          x - 20 * scale, y)
        painter.fillPath(flame_outer, QBrush(QColor(255, 140, 0, 200)))

        # Belső láng (sárga)
        inner_len = flame_length * 0.6
        flame_inner = QPainterPath()
        flame_inner.moveTo(x - 20 * scale, y)
        flame_inner.quadTo(x - (20 + inner_len) * scale, y - 4 * scale,
                          x - (22 + inner_len) * scale, y)
        flame_inner.quadTo(x - (20 + inner_len) * scale, y + 4 * scale,
                          x - 20 * scale, y)
        painter.fillPath(flame_inner, QBrush(QColor(255, 255, 100, 230)))

        # Rakéta test (világosszürke)
        body = QPainterPath()
        body.moveTo(x + 30 * scale, y)  # Orr
        body.quadTo(x + 25 * scale, y - 12 * scale, x - 5 * scale, y - 12 * scale)
        body.lineTo(x - 20 * scale, y - 8 * scale)
        body.lineTo(x - 20 * scale, y + 8 * scale)
        body.lineTo(x - 5 * scale, y + 12 * scale)
        body.quadTo(x + 25 * scale, y + 12 * scale, x + 30 * scale, y)
        painter.fillPath(body, QBrush(QColor(235, 235, 240)))

        # Orrkúp (piros)
        nose = QPainterPath()
        nose.moveTo(x + 30 * scale, y)
        nose.quadTo(x + 28 * scale, y - 8 * scale, x + 15 * scale, y - 10 * scale)
        nose.lineTo(x + 15 * scale, y + 10 * scale)
        nose.quadTo(x + 28 * scale, y + 8 * scale, x + 30 * scale, y)
        painter.fillPath(nose, QBrush(QColor(240, 90, 90)))

        # Felső szárny (piros)
        fin_top = QPainterPath()
        fin_top.moveTo(x - 10 * scale, y - 10 * scale)
        fin_top.lineTo(x - 20 * scale, y - 22 * scale)
        fin_top.lineTo(x - 22 * scale, y - 10 * scale)
        fin_top.closeSubpath()
        painter.fillPath(fin_top, QBrush(QColor(240, 90, 90)))

        # Alsó szárny (piros)
        fin_bottom = QPainterPath()
        fin_bottom.moveTo(x - 10 * scale, y + 10 * scale)
        fin_bottom.lineTo(x - 20 * scale, y + 22 * scale)
        fin_bottom.lineTo(x - 22 * scale, y + 10 * scale)
        fin_bottom.closeSubpath()
        painter.fillPath(fin_bottom, QBrush(QColor(240, 90, 90)))

        # Ablak (kék kör)
        painter.setBrush(QBrush(QColor(100, 180, 255)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(int(x + 5 * scale), int(y)), int(6 * scale), int(6 * scale))

        # Ablak fény (világosabb pont)
        painter.setBrush(QBrush(QColor(200, 230, 255)))
        painter.drawEllipse(QPoint(int(x + 3 * scale), int(y - 2 * scale)), int(2 * scale), int(2 * scale))

    def _draw_processing(self, painter: QPainter):
        """Processing animáció - rakéta + csillagok + vicces szöveg"""
        # Csillagok frissítése és rajzolása
        self._update_stars()
        self._draw_stars(painter)

        # Rakéta középen (kicsit balra, hogy a lángok is látszódjanak)
        rocket_x = self.width() // 2 + 15
        rocket_y = 38
        self._draw_rocket(painter, rocket_x, rocket_y)

        # Vicces szöveg alul - középre igazítva, szebb font
        painter.setPen(QPen(QColor(200, 200, 200)))
        font = QFont("Sans", 10)
        font.setItalic(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        text_x = (self.width() - fm.horizontalAdvance(self.current_message)) // 2
        painter.drawText(text_x, 78, self.current_message)

        # Frame növelés (animáció)
        self.animation_frame = (self.animation_frame + 1) % 60

    @Slot()
    def _next_message(self):
        """Következő üzenet - RANDOM választás"""
        self.current_message = random.choice(self.processing_messages)
        self.update()

    def _draw_text_preview(self, painter: QPainter):
        """Szöveg előnézet - fejléc + kisimult equalizer + szöveg alatta"""
        # 1. Fejléc rész (Recording + kisimult equalizer) - 50px magasság
        self._draw_header_with_flat_bars(painter)

        # 2. Elválasztó vonal
        padding = 15
        painter.setPen(QPen(QColor(60, 60, 60)))
        painter.drawLine(padding, 55, self.width() - padding, 55)

        # 3. Szöveg előnézet alatta
        max_chars = 40
        display_text = self.transcribed_text
        if len(display_text) > max_chars:
            display_text = display_text[:max_chars] + "..."

        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Sans", 10))
        painter.drawText(padding, 78, f'"{display_text}"')

        # 4. "Click to expand" gomb - zöldes háttérrel
        btn_text = t("popup_expand", self.ui_lang)
        btn_font = QFont("Sans", 9)
        painter.setFont(btn_font)
        fm = painter.fontMetrics()
        text_width = fm.horizontalAdvance(btn_text)

        btn_width = text_width + 35  # Hely az ikonnak is
        btn_height = 22
        btn_x = padding
        btn_y = self.height() - btn_height - 6

        # Gomb háttér - áttetsző zöld
        btn_rect = QRectF(btn_x, btn_y, btn_width, btn_height)
        btn_path = QPainterPath()
        btn_path.addRoundedRect(btn_rect, 4, 4)
        painter.fillPath(btn_path, QBrush(QColor(76, 175, 80, 60)))  # Zöld, áttetsző

        # Kattintás ikon - egérkurzor alakú
        icon_x = btn_x + 10
        icon_y = btn_y + btn_height // 2

        # Kurzor alakú ikon (nyíl)
        cursor = QPainterPath()
        cursor.moveTo(icon_x, icon_y - 7)       # Csúcs (felül)
        cursor.lineTo(icon_x + 5, icon_y + 1)   # Jobb alsó
        cursor.lineTo(icon_x + 2, icon_y + 1)   # Közép jobb
        cursor.lineTo(icon_x + 4, icon_y + 5)   # Nyél jobb
        cursor.lineTo(icon_x + 1, icon_y + 6)   # Nyél alja
        cursor.lineTo(icon_x - 1, icon_y + 3)   # Nyél bal
        cursor.lineTo(icon_x - 1, icon_y + 1)   # Közép bal
        cursor.lineTo(icon_x - 3, icon_y + 1)   # Bal alsó
        cursor.closeSubpath()
        painter.fillPath(cursor, QBrush(QColor(150, 220, 150)))

        # Gomb szöveg
        painter.setPen(QPen(QColor(180, 230, 180)))
        painter.drawText(int(btn_x + 22), int(btn_y + 15), btn_text)

        # 5. Visszaszámláló jobb oldalon - sárga háttérrel
        countdown_text = f"{self.countdown_remaining}s"
        painter.setFont(QFont("Sans", 9))
        fm = painter.fontMetrics()
        countdown_w = fm.horizontalAdvance(countdown_text) + 14
        countdown_h = 20
        countdown_x = self.width() - padding - countdown_w
        countdown_y = btn_y

        # Háttér - sárga/narancs
        countdown_rect = QRectF(countdown_x, countdown_y, countdown_w, countdown_h)
        countdown_path = QPainterPath()
        countdown_path.addRoundedRect(countdown_rect, 4, 4)
        painter.fillPath(countdown_path, QBrush(QColor(255, 193, 7, 180)))  # Sárga

        # Szöveg - sötét a sárga háttéren
        painter.setPen(QPen(QColor(50, 50, 50)))
        painter.drawText(int(countdown_x + 7), int(countdown_y + 14), countdown_text)

    def _draw_header_with_flat_bars(self, painter: QPainter):
        """Fejléc rész: Recording label + kisimult equalizer"""
        # Recording label (bal oldalon)
        circle_x = 15
        circle_y = 30
        circle_radius = 5

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(100, 100, 100)))  # Szürke kör (nem aktív)
        painter.drawEllipse(QPoint(circle_x, circle_y), circle_radius, circle_radius)

        painter.setPen(QPen(QColor(160, 160, 160)))
        painter.setFont(QFont("Sans", 9))
        painter.drawText(circle_x + 12, circle_y + 4, t("popup_done", self.ui_lang))

        # Kisimult equalizer (jobb oldalon, alacsony vonalak) - rövidebb, hogy a close gomb elférjen
        bar_width = 3
        bar_gap = 3
        bar_count = 20  # Kevesebb oszlop
        total_width = bar_count * (bar_width + bar_gap)
        start_x = self.width() - total_width - 35  # Több hely jobbra
        center_y = 30
        min_height = 3  # Alacsony, egyenletes magasság

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(100, 100, 100)))  # Szürke vonalak

        for i in range(bar_count):
            x = start_x + i * (bar_width + bar_gap)
            # Felső fél
            bar_path = QPainterPath()
            bar_path.addRoundedRect(QRectF(x, center_y - min_height, bar_width, min_height), 1, 1)
            painter.fillPath(bar_path, QBrush(QColor(100, 100, 100)))
            # Alsó fél
            bar_path2 = QPainterPath()
            bar_path2.addRoundedRect(QRectF(x, center_y, bar_width, min_height), 1, 1)
            painter.fillPath(bar_path2, QBrush(QColor(100, 100, 100)))

    def _draw_text_expanded(self, painter: QPainter):
        """Kibővített nézet - fejléc + teljes szöveg + Copy gomb + bezáró gomb"""
        padding = 15

        # 1. Fejléc rész (Done + kisimult equalizer)
        self._draw_header_with_flat_bars(painter)

        # Bezáró gomb - piros kör (macOS stílus) - jobb felső sarok, magasabban
        close_radius = 6
        close_x = self.width() - padding - close_radius
        close_y = 12
        self.close_btn_rect = QRectF(close_x - close_radius - 4, close_y - close_radius - 4,
                                      close_radius * 2 + 8, close_radius * 2 + 8)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 95, 87)))  # Piros (macOS)
        painter.drawEllipse(QPoint(int(close_x), int(close_y)), close_radius, close_radius)

        # 2. Elválasztó vonal
        painter.setPen(QPen(QColor(60, 60, 60)))
        painter.drawLine(padding, 55, self.width() - padding, 55)

        # 3. Teljes szöveg (több soros)
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.setFont(QFont("Sans", 10))

        # Szöveg tördelése
        text_width = self.width() - 2 * padding
        words = self.transcribed_text.split()
        lines = []
        current_line = ""
        fm = painter.fontMetrics()

        for word in words:
            test_line = current_line + (" " if current_line else "") + word
            if fm.horizontalAdvance(test_line) <= text_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Max 5 sor
        y = 72
        for i, line in enumerate(lines[:5]):
            painter.drawText(padding, y + i * 18, line)
        if len(lines) > 5:
            painter.drawText(padding, y + 5 * 18, "...")

        # 4. Copy gomb alul középen
        btn_width = 80
        btn_height = 28
        btn_x = (self.width() - btn_width) // 2
        btn_y = self.height() - btn_height - 10
        self.copy_btn_rect = QRectF(btn_x, btn_y, btn_width, btn_height)

        # Gomb háttér
        painter.setPen(QPen(QColor(80, 80, 80)))
        btn_path = QPainterPath()
        btn_path.addRoundedRect(self.copy_btn_rect, 6, 6)
        painter.fillPath(btn_path, QBrush(QColor(50, 50, 50)))
        painter.drawPath(btn_path)

        # Gomb szöveg
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setFont(QFont("Sans", 9))
        painter.drawText(int(btn_x + 22), int(btn_y + 18), t("popup_copy", self.ui_lang))

    def mousePressEvent(self, event):
        """Kattintás kezelése - állapot alapján"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()

            # TEXT_PREVIEW: kattintásra kibővítés
            if self.state == PopupState.TEXT_PREVIEW:
                self.auto_hide_timer.stop()
                self.countdown_timer.stop()
                self.state = PopupState.TEXT_EXPANDED
                self.setFixedSize(self.base_width, self.expanded_height)
                self.update()
                event.accept()
                return

            # TEXT_EXPANDED: gombok kezelése
            if self.state == PopupState.TEXT_EXPANDED:
                # X gomb - bezárás
                if self.close_btn_rect.contains(pos):
                    self.hide_popup()
                    event.accept()
                    return

                # Copy gomb - másolás
                if self.copy_btn_rect.contains(pos):
                    pyperclip.copy(self.transcribed_text)
                    self.hide_popup()
                    event.accept()
                    return

            # Egyébként drag
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Ablak húzása"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            self.saved_position = new_pos  # Pozíció mentése
            event.accept()

    @Slot()
    def show_popup(self):
        """Popup megjelenítése felvételhez"""
        print("[DEBUG] show_popup() SLOT meghívva!")
        self.state = PopupState.RECORDING
        self.auto_hide_timer.stop()  # Timer leállítása ha fut
        self.setFixedSize(self.base_width, self.base_height)
        if self.saved_position:
            self.move(self.saved_position)
        else:
            self._center_on_screen()
        print(f"[DEBUG] Popup méret: {self.width()}x{self.height()}, pozíció: {self.x()},{self.y()}")
        self.show()
        self.raise_()
        self.activateWindow()
        print(f"[DEBUG] Popup visible: {self.isVisible()}")

    @Slot()
    def show_processing(self):
        """Processing állapot megjelenítése (feldolgozás közben)"""
        self.state = PopupState.PROCESSING
        self.current_message = random.choice(self.processing_messages)
        self.animation_frame = 0
        self.message_timer.start(2000)  # 2 mp-ként új szöveg
        self.setFixedSize(self.base_width, self.base_height)
        self.update()

    @Slot()
    def show_pending_text(self):
        """Pending szöveg megjelenítése (QTimer callback)"""
        if hasattr(self, 'pending_text') and self.pending_text:
            self.show_text(self.pending_text)

    def show_text(self, text: str):
        """Szöveg megjelenítése transzkripció után"""
        print(f"[DEBUG] show_text() hívva, text='{text[:50]}...' state={self.state}")
        self.message_timer.stop()  # Processing timer leállítása
        self.transcribed_text = text
        self.state = PopupState.TEXT_PREVIEW
        self.setFixedSize(self.base_width, self.preview_height)
        self.update()
        print(f"[DEBUG] Állapot váltás után: state={self.state}")

        # Visszaszámláló indítása
        self.countdown_remaining = self.auto_hide_seconds
        self.countdown_timer.start(1000)  # Másodpercenként frissít

        # Auto-hide timer indítása
        self.auto_hide_timer.start(self.auto_hide_seconds * 1000)

    @Slot()
    def _update_countdown(self):
        """Visszaszámláló frissítése"""
        if self.countdown_remaining > 0:
            self.countdown_remaining -= 1
            self.update()  # Újrarajzolás
        else:
            self.countdown_timer.stop()

    @Slot()
    def _auto_hide(self):
        """Automatikus elrejtés timer után"""
        self.countdown_timer.stop()
        if self.state == PopupState.TEXT_PREVIEW:
            self.hide_popup()

    @Slot()
    def hide_popup(self):
        """Popup elrejtése"""
        self.state = PopupState.HIDDEN
        self.auto_hide_timer.stop()
        self.countdown_timer.stop()
        self.message_timer.stop()  # Processing timer leállítása
        self.hide()
        # Amplitude reset
        self.current_amplitude = 0.0
        self.smoothed_amplitude = 0.0


# Tesztelés
if __name__ == "__main__":
    import numpy as np
    import threading
    import time

    app = QApplication(sys.argv)

    # Teszt queue szimulált audio adatokkal
    test_queue = Queue()

    def generate_test_data():
        while True:
            # Szinusz hullám szimuláció
            amplitude = abs(np.sin(time.time() * 3)) * 0.5 + np.random.random() * 0.2
            test_queue.put(amplitude)
            time.sleep(0.05)

    # Háttér szál a teszt adatokhoz
    test_thread = threading.Thread(target=generate_test_data, daemon=True)
    test_thread.start()

    popup = RecordingPopup(test_queue)
    popup.show_popup()

    sys.exit(app.exec())
