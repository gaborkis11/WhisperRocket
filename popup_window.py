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


class RecordingPopup(QWidget):
    """Frameless popup ablak waveform vizualizációval"""

    def __init__(self, amplitude_queue: Queue):
        super().__init__()
        self.amplitude_queue = amplitude_queue
        self.waveform_data = [0.0] * 50  # 50 oszlop
        self.drag_position = None
        self.saved_position = None  # Session alatti pozíció memória

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
            # Összes elérhető amplitude érték feldolgozása
            while True:
                amplitude = self.amplitude_queue.get_nowait()
                # Hozzáadjuk az új értéket, eltávolítjuk a legrégebbit
                self.waveform_data.pop(0)
                self.waveform_data.append(amplitude)
        except Empty:
            pass

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
        """Waveform oszlopok rajzolása"""
        bar_count = len(self.waveform_data)
        bar_width = 4
        bar_gap = 2
        total_width = bar_count * (bar_width + bar_gap)

        # Középre igazítás
        start_x = (self.width() - total_width) // 2
        center_y = self.height() // 2
        max_height = 40  # Max oszlop magasság

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))  # Fehér oszlopok

        for i, amplitude in enumerate(self.waveform_data):
            # Amplitude normalizálás (0.0 - 1.0 közé)
            normalized = min(amplitude * 15, 1.0)  # Magasabb érzékenység
            bar_height = max(4, int(normalized * max_height))  # Min 4px

            x = start_x + i * (bar_width + bar_gap)
            y = center_y - bar_height // 2

            # Lekerekített oszlop
            bar_path = QPainterPath()
            bar_path.addRoundedRect(QRectF(x, y, bar_width, bar_height), 2, 2)
            painter.fillPath(bar_path, QBrush(QColor(255, 255, 255)))

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
        # Waveform reset
        self.waveform_data = [0.0] * 50


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
