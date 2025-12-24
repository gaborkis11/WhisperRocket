#!/usr/bin/env python3
"""
WhisperRocket Beállítások ablak v2
PyQt6 alapú modern UI tab-okkal
"""
import os
import json
import sys
import shutil
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox,
    QGroupBox, QFormLayout, QMessageBox, QTabWidget,
    QProgressBar, QListWidget, QListWidgetItem, QFrame, QSpinBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QKeySequence

from model_manager import (
    get_downloaded_models, get_active_model, delete_model,
    delete_all_unused, get_total_cache_size, get_freeable_size,
    format_size, is_model_downloaded
)
from download_manager import get_download_manager
from translations import t

# Konfiguráció útvonal
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')
DESKTOP_FILE = os.path.join(os.path.dirname(__file__), 'whisperrocket.desktop')
AUTOSTART_DIR = os.path.expanduser('~/.config/autostart')
AUTOSTART_FILE = os.path.join(AUTOSTART_DIR, 'whisperrocket.desktop')

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
    ("tiny", "Tiny (~150 MB) - Leggyorsabb"),
    ("base", "Base (~290 MB) - Gyors"),
    ("small", "Small (~490 MB) - Közepes"),
    ("medium", "Medium (~1.5 GB) - Jó"),
    ("large-v3-turbo", "Large-v3-turbo (~1.6 GB) - Gyors és jó"),
    ("large-v3", "Large-v3 (~6 GB) - Legjobb"),
]

# Device opciók
DEVICES = [
    ("cuda", "GPU (CUDA)"),
    ("cpu", "CPU"),
]

# UI nyelvek
UI_LANGUAGES = [
    ("en", "English"),
    ("hu", "Magyar"),
]


def detect_device():
    """CUDA elérhetőség automatikus detektálása"""
    try:
        import subprocess
        result = subprocess.run(['nvidia-smi'], capture_output=True, timeout=5)
        if result.returncode == 0:
            return "cuda", "float16"
    except:
        pass
    return "cpu", "int8"


def load_config():
    """Konfiguráció betöltése"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except:
        device, compute_type = detect_device()
        return {
            "hotkey": "alt+s",
            "model": "large-v3",
            "device": device,
            "compute_type": compute_type,
            "language": "hu",
            "sample_rate": 16000,
            "input_device": None,
            "output_device": None
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
            shutil.copy(DESKTOP_FILE, AUTOSTART_FILE)
    else:
        if os.path.exists(AUTOSTART_FILE):
            os.remove(AUTOSTART_FILE)


class SettingsWindow(QMainWindow):
    """Beállítások ablak tab-okkal"""

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.ui_lang = self.config.get("ui_language", "en")
        self.download_manager = get_download_manager()
        self.init_ui()

        # Progress frissítő timer
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_download_progress)
        self.progress_timer.start(500)  # 500ms

    def init_ui(self):
        """UI inicializálása"""
        self.setWindowTitle(t("settings_title", self.ui_lang))
        self.setFixedSize(500, 520)

        # Központi widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Cím
        title = QLabel(t("settings_title", self.ui_lang))
        title.setFont(QFont("Sans", 14, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_settings_tab(), t("tab_settings", self.ui_lang))
        self.tabs.addTab(self.create_models_tab(), t("tab_models", self.ui_lang))
        layout.addWidget(self.tabs)

        # Hotkey rögzítés állapota
        self.recording_hotkey = False

    def create_settings_tab(self):
        """Beállítások tab létrehozása"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Beállítások form
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # UI Nyelv (felület nyelve)
        self.ui_lang_combo = QComboBox()
        for code, name in UI_LANGUAGES:
            self.ui_lang_combo.addItem(name, code)
        self.set_combo_value(self.ui_lang_combo, self.ui_lang)
        form_layout.addRow(t("label_ui_language", self.ui_lang), self.ui_lang_combo)

        # Nyelv (Whisper nyelve)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES:
            self.language_combo.addItem(f"{name} ({code})", code)
        self.set_combo_value(self.language_combo, self.config.get("language", "hu"))
        form_layout.addRow(t("label_language", self.ui_lang), self.language_combo)

        # Hotkey
        hotkey_layout = QHBoxLayout()
        self.hotkey_edit = QLineEdit(self.config.get("hotkey", "alt+s"))
        self.hotkey_edit.setReadOnly(True)
        hotkey_layout.addWidget(self.hotkey_edit)

        self.record_btn = QPushButton(t("btn_record", self.ui_lang))
        self.record_btn.setFixedWidth(80)
        self.record_btn.clicked.connect(self.start_hotkey_recording)
        hotkey_layout.addWidget(self.record_btn)

        hotkey_widget = QWidget()
        hotkey_widget.setLayout(hotkey_layout)
        form_layout.addRow(t("label_hotkey", self.ui_lang), hotkey_widget)

        # Modell
        self.model_combo = QComboBox()
        for code, name in MODELS:
            downloaded = " ✓" if is_model_downloaded(code) else ""
            self.model_combo.addItem(f"{name}{downloaded}", code)
        self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        form_layout.addRow(t("label_model", self.ui_lang), self.model_combo)

        layout.addLayout(form_layout)

        # Letöltés progress panel
        self.progress_panel = QFrame()
        self.progress_panel.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Sunken)
        self.progress_panel.setStyleSheet("QFrame { background-color: #f0f0f0; border-radius: 5px; padding: 5px; }")
        progress_layout = QVBoxLayout(self.progress_panel)
        progress_layout.setSpacing(5)

        self.progress_title = QLabel("⬇ Letöltés: -")
        self.progress_title.setFont(QFont("Sans", 10, QFont.Weight.Bold))
        progress_layout.addWidget(self.progress_title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)

        self.progress_info = QLabel("0 MB / 0 MB  •  0 MB/s  •  -")
        self.progress_info.setStyleSheet("color: #666;")
        progress_layout.addWidget(self.progress_info)

        progress_btn_layout = QHBoxLayout()
        progress_btn_layout.addStretch()
        self.cancel_btn = QPushButton(t("btn_cancel", self.ui_lang))
        self.cancel_btn.setFixedWidth(80)
        self.cancel_btn.clicked.connect(self.cancel_download)
        progress_btn_layout.addWidget(self.cancel_btn)
        progress_layout.addLayout(progress_btn_layout)

        self.progress_panel.setVisible(False)
        layout.addWidget(self.progress_panel)

        # További beállítások
        form_layout2 = QFormLayout()
        form_layout2.setSpacing(10)

        # Device (GPU/CPU)
        self.device_combo = QComboBox()
        for code, name in DEVICES:
            self.device_combo.addItem(name, code)
        self.set_combo_value(self.device_combo, self.config.get("device", "cuda"))
        form_layout2.addRow(t("label_device", self.ui_lang), self.device_combo)

        # Popup megjelenítési idő
        self.popup_duration_spin = QSpinBox()
        self.popup_duration_spin.setRange(1, 30)
        self.popup_duration_spin.setSuffix(t("suffix_seconds", self.ui_lang))
        self.popup_duration_spin.setValue(self.config.get("popup_display_duration", 5))
        form_layout2.addRow(t("label_popup_duration", self.ui_lang), self.popup_duration_spin)

        layout.addLayout(form_layout2)

        # Autostart checkbox
        self.autostart_check = QCheckBox(t("autostart", self.ui_lang))
        self.autostart_check.setChecked(is_autostart_enabled())
        layout.addWidget(self.autostart_check)

        # Info label
        info_label = QLabel(t("info_restart", self.ui_lang))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Stretch
        layout.addStretch()

        # Gombok
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        save_btn = QPushButton(t("btn_save", self.ui_lang))
        save_btn.setFixedWidth(100)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)

        restart_btn = QPushButton(t("btn_save_restart", self.ui_lang))
        restart_btn.setFixedWidth(160)
        restart_btn.clicked.connect(self.save_and_restart)
        button_layout.addWidget(restart_btn)

        close_btn = QPushButton(t("btn_cancel", self.ui_lang))
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        return tab

    def create_models_tab(self):
        """Modellek tab létrehozása"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(12)

        # Cím
        title_label = QLabel(t("models_downloaded", self.ui_lang))
        title_label.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # Modellek lista
        self.models_list = QListWidget()
        self.models_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #e0e0e0;
            }
        """)
        layout.addWidget(self.models_list)

        # Összesítés
        self.storage_label = QLabel("-")
        self.storage_label.setStyleSheet("color: #666;")
        layout.addWidget(self.storage_label)

        # Info
        info_label = QLabel("ℹ " + t("info_active_model", self.ui_lang))
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info_label)

        # Gombok
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton(t("btn_refresh", self.ui_lang))
        refresh_btn.clicked.connect(self.refresh_models_list)
        button_layout.addWidget(refresh_btn)

        button_layout.addStretch()

        delete_selected_btn = QPushButton(t("btn_delete_selected", self.ui_lang))
        delete_selected_btn.clicked.connect(self.delete_selected_model)
        button_layout.addWidget(delete_selected_btn)

        delete_all_btn = QPushButton(t("btn_delete_all", self.ui_lang))
        delete_all_btn.clicked.connect(self.delete_all_unused_models)
        button_layout.addWidget(delete_all_btn)

        layout.addLayout(button_layout)

        # Lista feltöltése
        self.refresh_models_list()

        return tab

    def refresh_models_list(self):
        """Modellek lista frissítése"""
        self.models_list.clear()
        active_model = get_active_model()
        models = get_downloaded_models()

        for model in models:
            is_active = model["name"] == active_model
            prefix = "● " if is_active else "   "
            text = f"{prefix}{model['display_name']:20} {model['size_formatted']:>10}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, model["name"])

            if is_active:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                item.setForeground(Qt.GlobalColor.gray)

            self.models_list.addItem(item)

        # Összesítés frissítése
        total = format_size(get_total_cache_size())
        freeable = format_size(get_freeable_size())
        self.storage_label.setText(t("storage_info", self.ui_lang, total=total, free=freeable))

        # Modell combo frissítése is
        self.refresh_model_combo()

    def refresh_model_combo(self):
        """Modell dropdown frissítése letöltött jelölésekkel"""
        current_model = self.model_combo.currentData()
        self.model_combo.blockSignals(True)
        self.model_combo.clear()

        for code, name in MODELS:
            downloaded = " ✓" if is_model_downloaded(code) else ""
            self.model_combo.addItem(f"{name}{downloaded}", code)

        self.set_combo_value(self.model_combo, current_model)
        self.model_combo.blockSignals(False)

    def delete_selected_model(self):
        """Kijelölt modell törlése"""
        item = self.models_list.currentItem()
        if not item:
            QMessageBox.warning(self, t("dlg_warning", self.ui_lang), t("dlg_select_model", self.ui_lang))
            return

        model_name = item.data(Qt.ItemDataRole.UserRole)
        if model_name == get_active_model():
            QMessageBox.warning(self, t("dlg_warning", self.ui_lang), t("dlg_active_no_delete", self.ui_lang))
            return

        reply = QMessageBox.question(
            self,
            t("dlg_confirm", self.ui_lang),
            t("dlg_confirm_delete", self.ui_lang, model=model_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            success, message = delete_model(model_name)
            if success:
                QMessageBox.information(self, t("dlg_success", self.ui_lang), message)
                self.refresh_models_list()
            else:
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), message)

    def delete_all_unused_models(self):
        """Összes nem használt modell törlése"""
        freeable = get_freeable_size()
        if freeable == 0:
            QMessageBox.information(self, t("dlg_info", self.ui_lang), t("dlg_no_deletable", self.ui_lang))
            return

        reply = QMessageBox.question(
            self,
            t("dlg_confirm", self.ui_lang),
            t("dlg_confirm_delete_all", self.ui_lang, size=format_size(freeable)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted, freed, errors = delete_all_unused()
            if deleted > 0:
                QMessageBox.information(
                    self,
                    t("dlg_success", self.ui_lang),
                    t("dlg_deleted", self.ui_lang, count=deleted, size=format_size(freed))
                )
                self.refresh_models_list()
            elif errors:
                QMessageBox.warning(self, t("dlg_error", self.ui_lang), "\n".join(errors))

    def set_combo_value(self, combo, value):
        """ComboBox értékének beállítása"""
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                break

    def on_model_changed(self, index):
        """Modell váltás kezelése"""
        model_name = self.model_combo.currentData()

        # Ellenőrzés: folyamatban van-e letöltés
        if self.download_manager.is_downloading():
            reply = QMessageBox.question(
                self,
                t("dlg_warning", self.ui_lang),
                t("dlg_download_in_progress", self.ui_lang),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                # Visszaállítás az előző értékre
                self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))
                return
            else:
                self.download_manager.cancel_download()

        # Ha a modell nincs letöltve, kérdés
        if not is_model_downloaded(model_name):
            reply = QMessageBox.question(
                self,
                t("dlg_download", self.ui_lang),
                t("dlg_download_ask", self.ui_lang, model=model_name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.start_model_download(model_name)
            else:
                # Visszaállítás
                self.set_combo_value(self.model_combo, self.config.get("model", "large-v3"))

    def start_model_download(self, model_name):
        """Modell letöltés indítása"""
        self.progress_panel.setVisible(True)
        self.progress_title.setText("⬇ " + t("download_title", self.ui_lang, model=model_name))
        self.progress_bar.setValue(0)
        self.progress_info.setText(t("download_starting", self.ui_lang))

        self.download_manager.start_download(model_name)

    def update_download_progress(self):
        """Letöltés progress frissítése (timer által hívva)"""
        state = self.download_manager.get_state()

        if state.is_downloading:
            self.progress_panel.setVisible(True)
            self.progress_title.setText("⬇ " + t("download_title", self.ui_lang, model=state.model_name))

            # Ha a progress nem változott, pulzáló módba váltunk
            current_progress = state.downloaded_bytes
            if not hasattr(self, '_last_progress_bytes'):
                self._last_progress_bytes = 0
                self._stall_count = 0

            if current_progress == self._last_progress_bytes:
                self._stall_count += 1
            else:
                self._stall_count = 0
                self._last_progress_bytes = current_progress

            # Ha 4+ tick (2+ sec) óta nem változott, pulzáló mód
            if self._stall_count >= 4:
                # Indeterminate (pulzáló) progress bar
                if self.progress_bar.maximum() != 0:
                    self.progress_bar.setRange(0, 0)  # Pulzáló mód
                self.progress_info.setText(t("download_stall", self.ui_lang))
            else:
                # Normál progress bar
                if self.progress_bar.maximum() == 0:
                    self.progress_bar.setRange(0, 100)  # Vissza normál módba
                self.progress_bar.setValue(int(state.progress * 100))

                downloaded = self.download_manager.format_size(state.downloaded_bytes)
                total = self.download_manager.format_size(state.total_bytes)
                speed = self.download_manager.format_speed()
                eta = self.download_manager.format_eta()

                self.progress_info.setText(f"{downloaded} / {total}  •  {speed}  •  {eta}")

        elif state.completed:
            self.progress_panel.setVisible(True)
            self.progress_title.setText("✓ " + t("download_done", self.ui_lang, model=state.model_name))
            # Reset progress bar normál módba
            if self.progress_bar.maximum() == 0:
                self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.progress_info.setText(t("download_complete", self.ui_lang))
            self.cancel_btn.setVisible(False)
            # Reset stall counter
            self._last_progress_bytes = 0
            self._stall_count = 0

            # 3 másodperc után elrejtjük
            QTimer.singleShot(3000, self.hide_progress_panel)
            self.download_manager.clear_completed()
            self.refresh_model_combo()

        elif state.error:
            self.progress_panel.setVisible(True)
            self.progress_title.setText("✗ " + t("download_error", self.ui_lang, model=state.model_name))
            self.progress_info.setText(state.error)
            if self.cancel_btn.text() != t("btn_close", self.ui_lang):
                self.cancel_btn.setText(t("btn_close", self.ui_lang))
                try:
                    self.cancel_btn.clicked.disconnect()
                except:
                    pass
                self.cancel_btn.clicked.connect(self.close_error_panel)

        elif state.cancelled:
            self.progress_panel.setVisible(True)
            self.progress_title.setText(t("download_cancelled", self.ui_lang))
            self.progress_info.setText("")
            QTimer.singleShot(2000, self.hide_progress_panel)
            self.download_manager.clear_completed()

        else:
            # Ha nincs aktív letöltés és nincs model_name, elrejtjük
            if not state.model_name:
                self.progress_panel.setVisible(False)
            else:
                # "Beragadt" állapot: volt letöltés, de nem completed/error
                # Ellenőrizzük, hogy a modell tényleg letöltve van-e
                if is_model_downloaded(state.model_name):
                    self.progress_panel.setVisible(True)
                    self.progress_title.setText("✓ " + t("download_done", self.ui_lang, model=state.model_name))
                    self.progress_bar.setValue(100)
                    self.progress_info.setText(t("download_complete", self.ui_lang))
                    self.cancel_btn.setVisible(False)
                    QTimer.singleShot(3000, self.hide_progress_panel)
                    self.download_manager.clear_completed()
                    self.refresh_model_combo()

    def hide_progress_panel(self):
        """Progress panel elrejtése"""
        self.progress_panel.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.cancel_btn.setText(t("btn_cancel", self.ui_lang))
        # Reconnect to cancel_download
        try:
            self.cancel_btn.clicked.disconnect()
        except:
            pass
        self.cancel_btn.clicked.connect(self.cancel_download)

    def close_error_panel(self):
        """Hiba panel bezárása és állapot törlése"""
        self.download_manager.clear_error()
        self.hide_progress_panel()

    def cancel_download(self):
        """Letöltés megszakítása"""
        self.download_manager.cancel_download()

    def start_hotkey_recording(self):
        """Hotkey rögzítés indítása"""
        self.recording_hotkey = True
        self.hotkey_edit.setText(t("hotkey_press", self.ui_lang))
        self.hotkey_edit.setFocus()
        self.record_btn.setText("...")

    def keyPressEvent(self, event):
        """Billentyű lenyomás kezelése"""
        if self.recording_hotkey:
            # Modifier-only billentyűk figyelmen kívül hagyása
            modifier_keys = [
                Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift,
                Qt.Key.Key_Meta, Qt.Key.Key_AltGr
            ]
            if event.key() in modifier_keys:
                # Csak modifier lett lenyomva, várunk a tényleges billentyűre
                return

            modifiers = event.modifiers()
            parts = []

            if modifiers & Qt.KeyboardModifier.ControlModifier:
                parts.append("ctrl")
            if modifiers & Qt.KeyboardModifier.AltModifier:
                parts.append("alt")
            if modifiers & Qt.KeyboardModifier.ShiftModifier:
                parts.append("shift")

            # Tényleges billentyű neve - mindig event.key()-ből, mert event.text()
            # üres lehet Ctrl/Shift kombinációkkal
            key_name = QKeySequence(event.key()).toString().lower()

            if key_name:
                parts.append(key_name)

            if parts:
                hotkey = "+".join(parts)
                self.hotkey_edit.setText(hotkey)
                self.recording_hotkey = False
                self.record_btn.setText(t("btn_record", self.ui_lang))
        else:
            super().keyPressEvent(event)

    def save_settings(self):
        """Beállítások mentése"""
        self.config["language"] = self.language_combo.currentData()
        self.config["ui_language"] = self.ui_lang_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()
        self.config["popup_display_duration"] = self.popup_duration_spin.value()

        if self.config["device"] == "cuda":
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        save_config(self.config)
        set_autostart(self.autostart_check.isChecked())

        QMessageBox.information(
            self,
            t("dlg_saved", self.ui_lang),
            t("dlg_settings_saved", self.ui_lang)
        )
        self.close()

    def save_and_restart(self):
        """Beállítások mentése és alkalmazás újraindítása"""
        self.config["language"] = self.language_combo.currentData()
        self.config["ui_language"] = self.ui_lang_combo.currentData()
        self.config["hotkey"] = self.hotkey_edit.text()
        self.config["model"] = self.model_combo.currentData()
        self.config["device"] = self.device_combo.currentData()
        self.config["popup_display_duration"] = self.popup_duration_spin.value()

        if self.config["device"] == "cuda":
            self.config["compute_type"] = "float16"
        else:
            self.config["compute_type"] = "int8"

        save_config(self.config)
        set_autostart(self.autostart_check.isChecked())

        import subprocess
        import time

        subprocess.run(['pkill', '-f', 'whisper_gui.py'], capture_output=True)
        time.sleep(1)

        start_script = os.path.join(os.path.dirname(__file__), 'start.sh')
        subprocess.Popen(['bash', start_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        self.close()

    def closeEvent(self, event):
        """Ablak bezárásakor timer leállítása"""
        self.progress_timer.stop()
        super().closeEvent(event)


def show_settings():
    """Beállítások ablak megjelenítése"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = SettingsWindow()
    window.show()

    if not app.property("running"):
        app.setProperty("running", True)
        app.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())
