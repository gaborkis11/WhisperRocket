#!/usr/bin/env python3
"""
WhisperTalk Beállítások ablak
PyQt6 alapú modern UI
"""
import os
import json
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Konfiguráció útvonal
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
DESKTOP_FILE = os.path.join(os.path.dirname(__file__), 'whispertalk.desktop')
AUTOSTART_DIR = os.path.expanduser('~/.config/autostart')
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, 'whispertalk.desktop')

# Támogatott nyelvek
LANGUAGES = [
    ("hu", "Magyar"),
    ("en", "English"),
    ("de", "Deutsch"),
    ("fr", "Français"),
    ("es", "Español"),
    ("it", "Italiano"),
    ("pl", "Polski"),
    ("nl", "Nederlands"),
    ("pt", "Português"),
    ("ru", "Русский"),
    ("ja", "日本語"),
    ("zh", "中文"),
    ("ko", "한국어"),
]

# Whisper modellek
MODELS = [
    ("tiny", "Tiny (39MB) - Leggyorsabb"),
    ("base", "Base (74MB) - Gyors"),
    ("small", "Small (244MB) - Közepes"),
    ("medium", "Medium (769MB) - Jó"),
    ("large-v3-turbo", "Large-v3-turbo (1.6GB) - Gyors és jó"),
    ("large-v3", "Large-v3 (3GB) - Legjobb"),
]

# Device opciók
DEVICES = [
    ("cuda", "GPU (CUDA)"),
    ("cpu", "CPU"),
]


def load_config():
    """Konfiguráció betöltése"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        return {
            "hotkey": "alt+s",
            "model": "large-v3",
            "device": "cuda",
            "compute_type": "float16",
            "language": "hu",
            "sample_rate": 16000
        }


def save_config(config):
    """Konfiguráció mentése"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def is_autostart_enabled():
    """Ellenőrzi, hogy be van-e állítva autostart"""
    return os.path.exists(AUTOSTART_FILE)


def set_autostart(enabled):
    """Autostart be/kikapcsolása"""
    if enabled:
        os.makedirs(AUTOSTART_DIR, exist_ok=True)
        if os.path.exists(DESKTOP_FILE):
            import shutil
            shutil.copy(DESKTOP_FILE, AUTOSTART_FILE)
    else:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)


class SettingsWindow(QMainWindow):
    """Beállítások ablak"""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.init_ui()

    def init_ui(self):
        """UI inicializálása"""
        self.setWindowTitle("WhisperTalk Beállítások")
        self.setFixedSize(450, 400)

        # Központi widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Cím
        title = QLabel("WhisperTalk Beállítások")
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Beállítások csoport
        settings_group = QGroupBox("Beállítások")
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Nyelv
        self.language_combo = QComboBox()
        for code, name in LANGUAGES:
            self.language_combo.addItem(f"{name} ({code})", code)
        self.set_combo_value(self.language_combo, self.config.get("language", "hu"))
        form_layout.addRow("Nyelv:", self.language_combo)

        # Hotkey
        hotkey_layout = QHBoxLayout()
        self.hotkey_edit = QLineEdit(self.config.get("hotkey", "alt+s"))
        self.hotkey_edit.setReadOnly(True)
        self.hotkey_edit.setPlaceholderText("Kattints a Rögzít gombra...")
        hotkey_layout.addWidget(self.hotkey_edit)

        self.record_btn = QPushButton("Rögzít")
        self.record_btn.setFixedWidth(70)
        self.record_btn.clicked.connect(self.start_hotkey_recording)
        hotkey_layout.addWidget(self.record_btn)

        hotkey_widget = QWidget()
        hotkey_widget.setLayout(hotkey_layout)
        form_layout.addRow("Hotkey:", hotkey_widget)

        # Modell
        self.model_combo = QComboBox()
        for code, name in MODELS:
            self.model_combo.addItem(name, code)
        self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
        form_layout.addRow("Modell:", self.model_combo)

        # Device
        self.device_combo = QComboBox()
        for code, name in DEVICES:
            self.device_combo.addItem(name, code)
        self.set_combo_value(self.device_combo, self.config.get("device", "cuda"))
        form_layout.addRow("Device:", self.device_combo)

        settings_group.setLayout(form_layout)
        layout.addWidget(settings_group)

        # Autostart checkbox
        self.autostart_check = QCheckBox("Indítás rendszerindításkor")
        self.autostart_check.setChecked(is_autostart_enabled())
        layout.addWidget(self.autostart_check)

        # Info label
        info_label = QLabel("Megjegyzés: A modell váltás után újra kell indítani az alkalmazást.")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Gombok
        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton("Mentés")
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        restart_btn = QPushButton("Mentés és újraindítás")
        restart_btn.setFixedWidth(150)
        restart_btn.clicked.connect(self.save_and_restart)
        button_layout.addWidget(restart_btn)

        cancel_btn = QPushButton("Mégse")
        cancel_btn.setFixedWidth(100)
        cancel_btn.clicked.connect(self.close)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Hotkey rögzítés állapota
        self.recording_hotkey = False
        self.recorded_keys = set()

    def set_combo_value(self, combo, value):
        """ComboBox értékének beállítása"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def start_hotkey_recording(self):
        """Hotkey rögzítés indítása"""
        self.recording_hotkey = True
        self.recorded_keys = set()
        self.hotkey_edit.setText("Nyomd meg a billentyűkombinációt...")
        self.hotkey_edit.setFocus()
        self.record_btn.setText("...")

    def keyPressEvent(self, event):
        """Billentyű lenyomás kezelése"""
        if self.recording_hotkey:
            key = event.key()
            modifiers = event.modifiers()

            parts = []
            if modifiers & Qt.KeyboardModifier.ControlModifier:
                parts.append("ctrl")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                parts.append("alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                parts.append("shift")

            # Fő billentyű (ha nem módosító)
            key_name = event.text().lower()
            if key_name and key_name not in ['', ' ']:
                parts.append(key_name)

            if parts:
                hotkey = "+".join(parts)
                self.hotkey_edit.setText(hotkey)
                self.recording_hotkey = False
                self.record_btn.setText("Rögzít")
        else:
            super().keyPressEvent(event)

    def save_settings(self):
        """Beállítások mentése"""
        # Config frissítése
        self.config["language"] = self.language_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()

        # Compute type beállítása device alapján
        if self.config["device"] == "cuda":
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        # Mentés
        save_config(self.config)

        # Autostart
        set_autostart(self.autostart_check.isChecked())

        # Üzenet
        QMessageBox.information(
            self,
            "Mentve",
            "A beállítások elmentve!\n\nA változások az alkalmazás újraindítása után lépnek érvénybe."
        )
        self.close()

    def save_and_restart(self):
        """Beállítások mentése és alkalmazás újraindítása"""
        # Config frissítése
        self.config["language"] = self.language_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()

        # Compute type beállítása device alapján
        if self.config["device"] == "cuda":
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        # Mentés
        save_config(self.config)

        # Autostart
        set_autostart(self.autostart_check.isChecked())

        # Alkalmazás újraindítása
        import subprocess
        import time

        # Régi folyamat leállítása
        subprocess.run(['pkill', '-f', 'whisper_gui.py'], capture_output=True)
        time.sleep(1)

        # Új folyamat indítása
        start_script = os.path.join(os.path.dirname(__file__), 'start.sh')
        subprocess.Popen(['bash', start_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Ablak bezárása
        self.close()


def show_settings():
    """Beállítások ablak megjelenítése"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = SettingsWindow()
    window.show()

    # Ha nincs futó event loop, indítunk egyet
    if not app.property("running"):
        app.setProperty("running", True)
        app.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())
