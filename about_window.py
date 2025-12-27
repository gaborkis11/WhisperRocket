#!/usr/bin/env python3
"""
WhisperRocket - About Window
About ablak a System Tray menüből
"""

import os
import webbrowser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QFont


# Verzió
APP_VERSION = "1.0"

# Projekt mappa meghatározása
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(PROJECT_DIR, "assets", "icons", "whisperrocket_ico.png")


class AboutWindow(QDialog):
    """About ablak"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About")
        self.setFixedSize(320, 380)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._setup_ui()

    def _setup_ui(self):
        """UI felépítése"""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Ikon
        icon_label = QLabel()
        if os.path.exists(ICON_PATH):
            pixmap = QPixmap(ICON_PATH)
            scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label.setPixmap(scaled_pixmap)
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        # App név
        name_label = QLabel("WhisperRocket")
        name_label.setAlignment(Qt.AlignCenter)
        name_font = QFont()
        name_font.setPointSize(16)
        name_font.setBold(True)
        name_label.setFont(name_font)
        layout.addWidget(name_label)

        # Verzió
        version_label = QLabel(f"Version {APP_VERSION}")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #888;")
        layout.addWidget(version_label)

        # Elválasztó
        self._add_separator(layout)

        # Leírás
        desc_label = QLabel("Fast, local speech-to-text for Linux")
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #666;")
        layout.addWidget(desc_label)

        # Powered by
        powered_layout = QHBoxLayout()
        powered_layout.setAlignment(Qt.AlignCenter)
        powered_text = QLabel("Powered by")
        powered_text.setStyleSheet("color: #888;")
        powered_name = QLabel("Studio137")
        powered_font = QFont()
        powered_font.setBold(True)
        powered_name.setFont(powered_font)
        powered_layout.addWidget(powered_text)
        powered_layout.addWidget(powered_name)
        layout.addLayout(powered_layout)

        # Elválasztó
        self._add_separator(layout)

        # Developed by
        dev_title = QLabel("Developed by")
        dev_title.setAlignment(Qt.AlignCenter)
        dev_title.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(dev_title)

        dev_name = QLabel("Gabor Kis")
        dev_name.setAlignment(Qt.AlignCenter)
        dev_font = QFont()
        dev_font.setPointSize(12)
        dev_font.setBold(True)
        dev_name.setFont(dev_font)
        layout.addWidget(dev_name)

        # GitHub link
        github_btn = QPushButton("GitHub")
        github_btn.setCursor(Qt.PointingHandCursor)
        github_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #0066cc;
                border: none;
                font-size: 12px;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #0088ff;
            }
        """)
        github_btn.clicked.connect(self._open_github)
        layout.addWidget(github_btn, alignment=Qt.AlignCenter)

        # Spacer
        layout.addStretch()

        # Copyright
        copyright_label = QLabel("© 2025 Gabor Kis. All rights reserved.")
        copyright_label.setAlignment(Qt.AlignCenter)
        copyright_label.setStyleSheet("color: #999; font-size: 10px;")
        layout.addWidget(copyright_label)

    def _add_separator(self, layout):
        """Elválasztó vonal hozzáadása"""
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("background-color: #ddd;")
        layout.addWidget(line)

    def _open_github(self):
        """GitHub oldal megnyitása"""
        webbrowser.open("https://github.com/gaborkis11/WhisperRocket")


# Globális ablak referencia (hogy ne záródjon be azonnal)
_about_window = None


def show_about():
    """About ablak megjelenítése"""
    global _about_window
    if _about_window is None or not _about_window.isVisible():
        _about_window = AboutWindow()
    _about_window.show()
    _about_window.raise_()
    _about_window.activateWindow()


# Tesztelés
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)
    show_about()
    sys.exit(app.exec())
