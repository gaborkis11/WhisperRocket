#!/usr/bin/env python3
"""
WhisperTalk - Recording Popup Window
Valós idejű waveform vizualizáció felvétel közben
"""
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QPainterPath, QFont
from queue import Queue, Empty
import sys
import math
import random


class RecordingPopup(QWidget):
    """Frameless popup ablak waveform vizualizációval"""

    def __init__(self, amplitude_queue: Queue):
        super().__init__()
        self.amplitude_queue = amplitude_queue
        self.current_amplitude = 0.0  # Aktuális hangerő (nyers)
        self.smoothed_amplitude = 0.0  # Simított hangerő (megjelenítéshez)
        self.bar_count = 45  # Oszlopok száma
        self.drag_position = None
        self.saved_position = None  # Session alatti pozíció memória

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
        """Ablak rajzolása"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Háttér - sötét lekerekített téglalap
        bg_color = QColor(26, 26, 26, 240)  # #1a1a1a, kis átlátszóság
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), 12, 12)
        painter.fillPath(path, QBrush(bg_color))

        # Waveform rajzolás
        self._draw_waveform(painter)

        # "Recording" felirat piros körrel
        self._draw_recording_label(painter)

    def _draw_waveform(self, painter: QPainter):
        """Equalizer stílusú waveform - statikus, szimmetrikus oszlopok"""
        bar_width = 3
        bar_gap = 3
        total_width = self.bar_count * (bar_width + bar_gap)

        # Középre igazítás
        start_x = (self.width() - total_width) // 2
        center_y = self.height() // 2
        max_half_height = 25  # Max fél-magasság (fel ÉS le is ennyi)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))  # Fehér oszlopok

        # Simított amplitude normalizálás
        normalized_amp = min(self.smoothed_amplitude * 10, 1.0)

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
        """Recording felirat és piros kör"""
        # Piros kör
        circle_x = 15
        circle_y = self.height() - 20
        circle_radius = 5

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(239, 68, 68)))  # Piros
        painter.drawEllipse(QPoint(circle_x, circle_y), circle_radius, circle_radius)

        # "Recording" felirat
        painter.setPen(QPen(QColor(160, 160, 160)))  # Szürke szöveg
        painter.setFont(QFont("Sans", 9))
        painter.drawText(circle_x + 12, circle_y + 4, "Recording")

    def mousePressEvent(self, event):
        """Drag kezdése"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        """Ablak húzása"""
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            new_pos = event.globalPosition().toPoint() - self.drag_position
            self.move(new_pos)
            self.saved_position = new_pos  # Pozíció mentése
            event.accept()

    def show_popup(self):
        """Popup megjelenítése"""
        if self.saved_position:
            self.move(self.saved_position)
        else:
            self._center_on_screen()
        self.show()
        self.raise_()
        self.activateWindow()

    def hide_popup(self):
        """Popup elrejtése"""
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
