#!/usr/bin/env python3
"""
History Viewer - Önálló ablak a history bejegyzés megjelenítéséhez
Külön processben fut, hogy elkerüljük a QSystemTrayIcon crash-t
"""

import sys
import json
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from datetime import datetime

class HistoryViewer(QDialog):
    def __init__(self, entry_json: str):
        super().__init__()
        self.entry = json.loads(entry_json)
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("History")
        self.setMinimumSize(500, 350)
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(12)

        # Fejléc
        timestamp = self.entry.get("timestamp", "")
        try:
            dt = datetime.fromisoformat(timestamp)
            header_text = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            header_text = timestamp

        duration = self.entry.get("duration_sec", 0)
        language = self.entry.get("language", "")
        if duration:
            header_text += f"  •  {duration:.1f}s"
        if language:
            header_text += f"  •  {language.upper()}"

        header = QLabel(header_text)
        header.setFont(QFont("sans-serif", 10))
        header.setStyleSheet("color: #888888;")
        layout.addWidget(header)

        # Szöveg
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(self.entry.get("text", ""))
        self.text_edit.setFont(QFont("sans-serif", 11))
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.text_edit, 1)

        # Gombok
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.copy_button = QPushButton("Másolás")
        self.copy_button.setFixedWidth(100)
        self.copy_button.clicked.connect(self.copy_to_clipboard)
        self.copy_button.setStyleSheet("""
            QPushButton {
                background-color: #4a90d9;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a9fe9; }
        """)
        button_layout.addWidget(self.copy_button)

        close_button = QPushButton("Bezár")
        close_button.setFixedWidth(100)
        close_button.clicked.connect(self.close)
        close_button.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
            }
            QPushButton:hover { background-color: #666666; }
        """)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        # Sötét téma
        self.setStyleSheet("""
            QDialog { background-color: #1e1e1e; }
            QLabel { color: #e0e0e0; }
        """)

    def copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.entry.get("text", ""))
        self.copy_button.setText("Másolva!")


def main():
    if len(sys.argv) < 2:
        print("Usage: history_viewer.py <entry_json>")
        sys.exit(1)

    app = QApplication(sys.argv)
    entry_json = sys.argv[1]

    dialog = HistoryViewer(entry_json)
    dialog.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
